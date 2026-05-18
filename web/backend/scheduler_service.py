"""Scheduled batch analysis service with cron-based scheduling and concurrent execution."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from croniter import croniter

from .watchlist_manager import WatchlistManager
from .holdings_router import get_holdings_manager
from .holdings_manager import format_holdings_for_prompt
from .task_manager import get_task_manager
from .stream_adapter import start_analysis
from .models import TaskStatus

logger = logging.getLogger("tradingagents.web.scheduler")

TERMINAL_TASK_STATUSES = {
    TaskStatus.COMPLETED.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
}


class SchedulerService:
    """Cron-based scheduler for batch stock analysis."""

    def __init__(self, watchlist_manager: WatchlistManager):
        self._wm = watchlist_manager
        self._task: Optional[asyncio.Task] = None
        self._batch_tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self):
        """Start the scheduler background loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="scheduler_loop")
        logger.info("Scheduler service started")

    async def stop(self):
        """Stop the scheduler background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler service stopped")

    async def _loop(self):
        """Main scheduler loop: check cron every 30 seconds."""
        while self._running:
            try:
                await self._check_and_trigger()
            except Exception:
                logger.exception("Scheduler loop error")
            await asyncio.sleep(30)

    async def _check_and_trigger(self):
        schedule = self._wm.get_schedule()
        if not schedule or not schedule.get("enabled"):
            self._wm.update_schedule_next_run(None)
            return

        cron_expr = schedule.get("cron_expression", "0 9 * * 1-5")
        now = datetime.now().astimezone()
        try:
            next_run = croniter(cron_expr, now).get_next(datetime)
            self._wm.update_schedule_next_run(next_run.isoformat())
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid cron expression: {cron_expr} - {e}")
            return

        # Trigger only after the most recent scheduled time, with a short catch-up
        # window for scheduler loop delays or brief process stalls.
        scheduled_at = croniter(cron_expr, now + timedelta(seconds=1)).get_prev(datetime)
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=now.tzinfo)
        else:
            scheduled_at = scheduled_at.astimezone(now.tzinfo)

        seconds_since_scheduled = (now - scheduled_at).total_seconds()
        if seconds_since_scheduled < 0 or seconds_since_scheduled > 300:
            return

        last_run_str = schedule.get("last_run_at")

        # Check we haven't already run for this scheduled time
        if last_run_str:
            try:
                last_run = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=now.tzinfo)
                else:
                    last_run = last_run.astimezone(now.tzinfo)
                if scheduled_at <= last_run < next_run:
                    return
            except Exception as exc:
                logger.warning(
                    "Failed to parse previous scheduled batch run time",
                    exc_info=(type(exc), exc, exc.__traceback__),
                    extra={"extra_data": {
                        "stage": "scheduler_parse_last_run",
                        "last_run_at": last_run_str,
                    }},
                )

        # Trigger batch analysis
        logger.info(f"Triggering scheduled batch analysis (cron: {cron_expr})")
        await self.run_batch(triggered_by="schedule")
        self._wm.update_schedule_last_run()

    async def run_batch(self, triggered_by: str = "manual") -> str:
        """Run batch analysis on all enabled watchlist stocks. Returns batch_id."""
        stocks = self._wm.list_stocks(enabled_only=True)
        if not stocks:
            raise ValueError("自选股列表为空")

        batch_id = str(uuid.uuid4())
        total = len(stocks)
        self._wm.create_batch_run(batch_id, triggered_by, total)

        task = asyncio.create_task(
            self._execute_batch(batch_id, stocks),
            name=f"batch_analysis_{batch_id}",
        )
        self._batch_tasks[batch_id] = task
        task.add_done_callback(lambda t, bid=batch_id: self._on_batch_done(bid, t))

        return batch_id

    async def _execute_batch(self, batch_id: str, stocks: list[dict]):
        """Run a batch in the background and finalize its aggregate status."""
        # Get schedule config
        schedule = self._wm.get_schedule()
        max_concurrency = schedule.get("max_concurrency", 2)
        config = schedule.get("config", {})
        analysts = config.get("analysts", ["market", "social", "news", "fundamentals"])
        max_debate_rounds = config.get("max_debate_rounds")
        max_risk_discuss_rounds = config.get("max_risk_discuss_rounds")

        trade_date = datetime.now().strftime("%Y-%m-%d")

        # Create tasks in the background and hold the semaphore until each task
        # reaches a terminal state so schedule max_concurrency controls the
        # actual number of analyses running for this batch.
        semaphore = asyncio.Semaphore(max_concurrency)
        tm = get_task_manager()

        # Check for existing completed tasks on same date to skip duplicates
        existing_tasks = {}
        for stock in stocks:
            existing = self._find_existing_task(stock["ticker"], trade_date)
            if existing:
                existing_tasks[stock["ticker"]] = existing

        async def _run_one(stock: dict):
            ticker = stock["ticker"]
            # Skip if already analyzed today
            if ticker in existing_tasks:
                return existing_tasks[ticker]["task_id"], "skipped"

            task_id = None
            async with semaphore:
                try:
                    task_id = tm.create_task(
                        ticker=ticker,
                        trade_date=trade_date,
                        config={
                            "analysts": analysts,
                            "max_debate_rounds": max_debate_rounds,
                            "max_risk_discuss_rounds": max_risk_discuss_rounds,
                        },
                    )
                    # Link task to batch
                    self._link_task_to_batch(task_id, batch_id)

                    config_override = {}
                    if max_debate_rounds is not None:
                        config_override["max_debate_rounds"] = max_debate_rounds
                    if max_risk_discuss_rounds is not None:
                        config_override["max_risk_discuss_rounds"] = max_risk_discuss_rounds

                    holding = get_holdings_manager().get_holding_by_ticker(ticker)
                    portfolio_holdings = format_holdings_for_prompt(holding)

                    await start_analysis(
                        task_id=task_id,
                        ticker=ticker,
                        trade_date=trade_date,
                        analysts=analysts,
                        config_override=config_override if config_override else None,
                        portfolio_holdings=portfolio_holdings,
                    )
                    await self._wait_for_task_completion(task_id)
                    return task_id, "submitted"
                except Exception as exc:
                    logger.exception("Failed to submit batch analysis task", extra={"extra_data": {
                        "batch_id": batch_id,
                        "ticker": ticker,
                        "task_id": task_id,
                    }})
                    if task_id:
                        tm.update_status(task_id, TaskStatus.FAILED, error=str(exc))
                        return task_id, "failed"
                    return None, "failed"

        futures = [_run_one(stock) for stock in stocks]
        results = await asyncio.gather(*futures, return_exceptions=True)
        submission_failures = sum(
            1
            for result in results
            if isinstance(result, Exception) or result[1] == "failed"
        )
        skipped = sum(
            1
            for result in results
            if not isinstance(result, Exception) and result[1] == "skipped"
        )

        self._finalize_batch_run(batch_id, skipped=skipped, submission_failures=submission_failures)

    async def _wait_for_task_completion(self, task_id: str, poll_interval: float = 5.0):
        """Poll a task until it reaches a terminal status."""
        tm = get_task_manager()
        while True:
            task = tm.get_task(task_id)
            if task and task.get("status") in TERMINAL_TASK_STATUSES:
                return
            await asyncio.sleep(poll_interval)

    def _finalize_batch_run(self, batch_id: str, skipped: int = 0, submission_failures: int = 0):
        tasks = self._wm.get_batch_tasks(batch_id)
        completed_tasks = sum(1 for t in tasks if t["status"] == TaskStatus.COMPLETED.value)
        failed_tasks = sum(1 for t in tasks if t["status"] in (TaskStatus.FAILED.value, TaskStatus.CANCELLED.value))
        completed = completed_tasks + skipped
        failed = failed_tasks + submission_failures
        self._wm.update_batch_task_count(batch_id, completed, failed)

        if failed == 0:
            status = "completed"
        elif completed == 0:
            status = "failed"
        else:
            status = "partial_failure"
        self._wm.finish_batch_run(batch_id, status)

    def _on_batch_done(self, batch_id: str, task: asyncio.Task):
        self._batch_tasks.pop(batch_id, None)
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            self._wm.finish_batch_run(batch_id, "partial_failure", error="批量分析被取消")
            return

        if exc is not None:
            logger.exception("Batch analysis failed", exc_info=(type(exc), exc, exc.__traceback__))
            self._wm.finish_batch_run(batch_id, "failed", error=str(exc))

    async def _wait_for_batch_completion(self, batch_id: str, poll_interval: float = 5.0):
        """Poll until all tasks in a batch are done, then update batch status."""
        while True:
            tasks = self._wm.get_batch_tasks(batch_id)
            if not tasks:
                self._wm.finish_batch_run(batch_id, "completed")
                break

            all_done = all(
                t["status"] in TERMINAL_TASK_STATUSES
                for t in tasks
            )
            if all_done:
                completed = sum(1 for t in tasks if t["status"] == "completed")
                failed = sum(1 for t in tasks if t["status"] in ("failed", "cancelled"))
                self._wm.update_batch_task_count(batch_id, completed, failed)

                if failed == 0:
                    self._wm.finish_batch_run(batch_id, "completed")
                elif completed == 0:
                    self._wm.finish_batch_run(batch_id, "failed")
                else:
                    self._wm.finish_batch_run(batch_id, "partial_failure")
                break

            # Also count currently running tasks that have active runners
            running = sum(1 for t in tasks if t["status"] == "running")
            pending = sum(1 for t in tasks if t["status"] == "pending")
            self._wm.update_batch_task_count(
                batch_id,
                sum(1 for t in tasks if t["status"] == "completed"),
                sum(1 for t in tasks if t["status"] in ("failed", "cancelled")),
            )

            await asyncio.sleep(poll_interval)

    def _link_task_to_batch(self, task_id: str, batch_id: str):
        """Link a task to a batch run in the database."""
        import sqlite3
        from pathlib import Path
        from .config import WEB_CONFIG

        db_path = Path(WEB_CONFIG["db_path"])
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE tasks SET batch_id = ? WHERE task_id = ?", (batch_id, task_id))
            conn.commit()

    def _find_existing_task(self, ticker: str, trade_date: str) -> Optional[dict]:
        """Find a completed task for this ticker + date."""
        import sqlite3
        from pathlib import Path
        from .config import WEB_CONFIG

        db_path = Path(WEB_CONFIG["db_path"])
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT task_id, status FROM tasks
                   WHERE ticker = ? AND trade_date = ? AND status = 'completed'
                   ORDER BY created_at DESC LIMIT 1""",
                (ticker, trade_date),
            ).fetchone()
        return dict(row) if row else None

    def get_status(self) -> dict:
        """Get current scheduler status."""
        schedule = self._wm.get_schedule()
        return {
            "running": self._running,
            "enabled": schedule.get("enabled", False) if schedule else False,
            "cron_expression": schedule.get("cron_expression", "") if schedule else "",
            "next_run_at": schedule.get("next_run_at"),
            "last_run_at": schedule.get("last_run_at"),
        }


# Global instance
_scheduler: Optional[SchedulerService] = None


def get_scheduler() -> Optional[SchedulerService]:
    return _scheduler


def create_scheduler(watchlist_manager: WatchlistManager) -> SchedulerService:
    global _scheduler
    _scheduler = SchedulerService(watchlist_manager)
    return _scheduler
