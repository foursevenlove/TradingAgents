import asyncio
from datetime import datetime as real_datetime, timezone, timedelta

from web.backend.config import WEB_CONFIG
import web.backend.scheduler_service as scheduler_module
import web.backend.task_manager as task_manager_module
from web.backend.models import TaskStatus
from web.backend.scheduler_service import SchedulerService
from web.backend.task_manager import get_task_manager
from web.backend.watchlist_manager import WatchlistManager


class RecordingScheduler(SchedulerService):
    def __init__(self, watchlist_manager):
        super().__init__(watchlist_manager)
        self.triggered_by = []

    async def run_batch(self, triggered_by: str = "manual") -> str:
        self.triggered_by.append(triggered_by)
        return "batch-id"


def _set_db(monkeypatch, tmp_path):
    monkeypatch.setitem(WEB_CONFIG, "db_path", str(tmp_path / "tasks.db"))
    monkeypatch.setattr(task_manager_module, "_task_manager", None)
    monkeypatch.setattr(scheduler_module, "get_task_manager", get_task_manager)


def _patch_now(monkeypatch, fixed_now):
    class FixedDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

        @classmethod
        def fromisoformat(cls, value):
            return real_datetime.fromisoformat(value)

    monkeypatch.setattr(scheduler_module, "datetime", FixedDatetime)


def test_scheduler_does_not_trigger_before_scheduled_time(monkeypatch, tmp_path):
    _set_db(monkeypatch, tmp_path)
    wm = WatchlistManager()
    wm.update_schedule(enabled=True, cron_expression="0 9 * * *", max_concurrency=2, config={})
    scheduler = RecordingScheduler(wm)

    _patch_now(
        monkeypatch,
        real_datetime(2026, 5, 17, 8, 59, 30, tzinfo=timezone(timedelta(hours=8))),
    )

    asyncio.run(scheduler._check_and_trigger())

    assert scheduler.triggered_by == []


def test_scheduler_triggers_after_scheduled_time(monkeypatch, tmp_path):
    _set_db(monkeypatch, tmp_path)
    wm = WatchlistManager()
    wm.update_schedule(enabled=True, cron_expression="0 9 * * *", max_concurrency=2, config={})
    scheduler = RecordingScheduler(wm)

    _patch_now(
        monkeypatch,
        real_datetime(2026, 5, 17, 9, 0, 30, tzinfo=timezone(timedelta(hours=8))),
    )

    asyncio.run(scheduler._check_and_trigger())

    assert scheduler.triggered_by == ["schedule"]


def test_batch_finishes_when_all_stocks_are_skipped(monkeypatch, tmp_path):
    _set_db(monkeypatch, tmp_path)
    wm = WatchlistManager()
    tm = get_task_manager()
    stock = wm.add_stock("600000.SH", "浦发银行")
    assert stock["enabled"] == 1

    task_id = tm.create_task("600000.SH", real_datetime.now().strftime("%Y-%m-%d"), {})
    tm.update_status(task_id, TaskStatus.COMPLETED)

    scheduler = SchedulerService(wm)

    async def run_batch_to_completion():
        batch_id = await scheduler.run_batch(triggered_by="manual")
        await scheduler._batch_tasks[batch_id]
        return batch_id

    batch_id = asyncio.run(run_batch_to_completion())

    batch = wm.get_batch_run(batch_id)
    assert batch["status"] == "completed"
    assert batch["completed_count"] == 1
    assert batch["failed_count"] == 0
