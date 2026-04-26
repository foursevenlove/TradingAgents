"""Scheduled batch analysis service with cron-based scheduling and concurrent execution."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from croniter import croniter

from .watchlist_manager import WatchlistManager
from .task_manager import get_task_manager
from .stream_adapter import start_analysis

logger = logging.getLogger(__name__)


class SchedulerService:
    """Cron-based scheduler for batch stock analysis."""

    def __init__(self, watchlist_manager: WatchlistManager):
        self._wm = watchlist_manager
        self._task: Optional[asyncio.Task] = None
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
        try:
            cr = croniter(cron_expr, datetime.now())
            next_run = cr.get_next(datetime)
            self._wm.update_schedule_next_run(next_run.isoformat())
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid cron expression: {cron_expr} - {e}")
            return

        # Check if it's time to run (within 60s window)
        last_run_str = schedule.get("last_run_at")
        now = datetime.now(timezone.utc)

        # Parse next_run as naive UTC for comparison
        next_run_utc = next_run.replace(tzinfo=timezone.utc) if next_run.tzinfo is None else next_run.astimezone(timezone.utc)
        diff = (next_run_utc - now).total_seconds()

        if diff > 60:
            return  # Not time yet

        # Check we haven't already run for this scheduled time
        if last_run_str:
            try:
                last_run = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
                # If last run was within 5 minutes of the scheduled time, skip
                if abs((last_run - next_run_utc).total_seconds()) < 300:
                    return
            except Exception:
                pass

        # Trigger batch analysis
        logger.info(f"Triggering scheduled batch analysis (cron: {cron_expr})")
        self._wm.update_schedule_last_run()
        await self.run_batch(triggered_by="schedule")

    async def run_batch(self, triggered_by: str = "manual") -> str:
        """Run batch analysis on all enabled watchlist stocks. Returns batch_id."""
        stocks = self._wm.list_stocks(enabled_only=True)
        if not stocks:
            raise ValueError("自选股列表为空")

        batch_id = str(uuid.uuid4())
        total = len(stocks)
        self._wm.create_batch_run(batch_id, triggered_by, total)

        # Get schedule config
        schedule = self._wm.get_schedule()
        max_concurrency = schedule.get("max_concurrency", 2)
        config = schedule.get("config", {})
        analysts = config.get("analysts", ["market", "social", "news", "fundamentals"])
        max_debate_rounds = config.get("max_debate_rounds")
        max_risk_discuss_rounds = config.get("max_risk_discuss_rounds")

        trade_date = datetime.now().strftime("%Y-%m-%d")

        # Create all tasks first, then run with semaphore
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

            async with semaphore:
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

                await start_analysis(
                    task_id=task_id,
                    ticker=ticker,
                    trade_date=trade_date,
                    analysts=analysts,
                    config_override=config_override if config_override else None,
                )

                # Wait for completion by polling
                return task_id, "submitted"

        # Fire all tasks (semaphore controls concurrency)
        futures = [_run_one(stock) for stock in stocks]
        results = await asyncio.gather(*futures, return_exceptions=True)

        # Wait for all submitted tasks to actually complete, then tally
        await self._wait_for_batch_completion(batch_id)

        return batch_id

    async def _wait_for_batch_completion(self, batch_id: str, poll_interval: float = 5.0):
        """Poll until all tasks in a batch are done, then update batch status."""
        from .stream_adapter import get_runner

        while True:
            tasks = self._wm.get_batch_tasks(batch_id)
            if not tasks:
                break

            all_done = all(
                t["status"] in ("completed", "failed", "cancelled")
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
