"""Watchlist, schedule config, and batch run CRUD."""
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import WEB_CONFIG


logger = logging.getLogger("tradingagents.web.watchlist")


class WatchlistManager:
    """Manages watchlist stocks, schedule config, and batch run records."""

    def __init__(self):
        self._db_path = Path(WEB_CONFIG["db_path"])
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # Watchlist table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT UNIQUE NOT NULL,
                    name TEXT DEFAULT '',
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Schedule config table (single row) - 默认每天 09:00 执行
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    enabled INTEGER DEFAULT 0,
                    cron_expression TEXT NOT NULL DEFAULT '0 9 * * *',
                    next_run_at TEXT,
                    last_run_at TEXT,
                    max_concurrency INTEGER DEFAULT 2,
                    config TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Batch runs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_runs (
                    batch_id TEXT PRIMARY KEY,
                    triggered_at TEXT NOT NULL,
                    triggered_by TEXT NOT NULL DEFAULT 'manual',
                    status TEXT NOT NULL DEFAULT 'running',
                    total_stocks INTEGER NOT NULL,
                    completed_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    completed_at TEXT,
                    error TEXT
                )
            """)

            # Add batch_id column to tasks if not exists
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN batch_id TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists

            # Initialize default schedule row (每天 09:00 执行)
            now = datetime.utcnow().isoformat() + "Z"
            existing = conn.execute("SELECT id FROM schedule WHERE id = 1").fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO schedule (id, enabled, cron_expression, max_concurrency, config, created_at, updated_at) VALUES (1, 0, '0 9 * * *', 2, '{}', ?, ?)",
                    (now, now),
                )

            conn.commit()

    # ── Watchlist CRUD ──────────────────────────────────────────────

    def list_stocks(self, enabled_only: bool = False) -> List[dict]:
        with self._get_conn() as conn:
            where = " WHERE enabled = 1" if enabled_only else ""
            rows = conn.execute(
                f"SELECT * FROM watchlist{where} ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_stock(self, ticker: str, name: str = "") -> dict:
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO watchlist (ticker, name, enabled, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                    (ticker, name, now, now),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Already exists, update name
                conn.execute(
                    "UPDATE watchlist SET name = ?, enabled = 1, updated_at = ? WHERE ticker = ?",
                    (name, now, ticker),
                )
                conn.commit()
            row = conn.execute("SELECT * FROM watchlist WHERE ticker = ?", (ticker,)).fetchone()
        return dict(row)

    def remove_stock(self, stock_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM watchlist WHERE id = ?", (stock_id,))
            conn.commit()
        return cur.rowcount > 0

    def update_stock(self, stock_id: int, enabled: bool) -> bool:
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE watchlist SET enabled = ?, updated_at = ? WHERE id = ?",
                (1 if enabled else 0, now, stock_id),
            )
            conn.commit()
        return cur.rowcount > 0

    # ── Schedule Config ─────────────────────────────────────────────

    def get_schedule(self) -> dict:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM schedule WHERE id = 1").fetchone()
        if not row:
            return {}
        result = dict(row)
        # Convert SQLite integer booleans to Python booleans
        if "enabled" in result:
            result["enabled"] = bool(result["enabled"])
        if result.get("config") and isinstance(result["config"], str):
            try:
                result["config"] = json.loads(result["config"])
            except Exception as exc:
                logger.warning(
                    "Failed to parse schedule config JSON, using empty config",
                    exc_info=(type(exc), exc, exc.__traceback__),
                    extra={"extra_data": {
                        "stage": "watchlist_schedule_config_parse",
                        "raw_config": result.get("config"),
                    }},
                )
                result["config"] = {}
        return result

    def update_schedule(self, enabled: bool, cron_expression: str, max_concurrency: int, config: dict = None) -> dict:
        now = datetime.utcnow().isoformat() + "Z"
        config_json = json.dumps(config or {}, ensure_ascii=False)
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE schedule SET enabled = ?, cron_expression = ?, max_concurrency = ?,
                   config = ?, updated_at = ? WHERE id = 1""",
                (1 if enabled else 0, cron_expression, max_concurrency, config_json, now),
            )
            conn.commit()
        return self.get_schedule()

    def update_schedule_next_run(self, next_run_at: Optional[str]):
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE schedule SET next_run_at = ?, updated_at = ? WHERE id = 1",
                (next_run_at, now),
            )
            conn.commit()

    def update_schedule_last_run(self):
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE schedule SET last_run_at = ?, updated_at = ? WHERE id = 1",
                (now, now),
            )
            conn.commit()

    # ── Batch Runs ──────────────────────────────────────────────────

    def create_batch_run(self, batch_id: str, triggered_by: str, total_stocks: int) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO batch_runs (batch_id, triggered_at, triggered_by, status, total_stocks)
                   VALUES (?, ?, ?, 'running', ?)""",
                (batch_id, now, triggered_by, total_stocks),
            )
            conn.commit()

    def update_batch_task_count(self, batch_id: str, completed: int, failed: int):
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE batch_runs SET completed_count = ?, failed_count = ? WHERE batch_id = ?""",
                (completed, failed, batch_id),
            )
            conn.commit()

    def finish_batch_run(self, batch_id: str, status: str, error: str = None):
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE batch_runs SET status = ?, completed_at = ?, error = ? WHERE batch_id = ?""",
                (status, now, error, batch_id),
            )
            conn.commit()

    def list_batch_runs(self, limit: int = 50, offset: int = 0) -> List[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM batch_runs ORDER BY triggered_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_batch_run(self, batch_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM batch_runs WHERE batch_id = ?", (batch_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_batch_tasks(self, batch_id: str) -> List[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT task_id, ticker, trade_date, status, created_at, completed_at, signal, error
                   FROM tasks WHERE batch_id = ? ORDER BY created_at""",
                (batch_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_skipped_stocks(self, batch_id: str, trade_date: str) -> List[dict]:
        """Get stocks that were skipped because they already had completed tasks today."""
        # Get the batch info to find which stocks were intended
        batch = self.get_batch_run(batch_id)
        if not batch:
            return []

        # Get all enabled stocks at the time (from watchlist)
        stocks = self.list_stocks(enabled_only=True)

        # Get tasks that were actually created for this batch
        batch_tasks = self.get_batch_tasks(batch_id)
        analyzed_tickers = {t["ticker"] for t in batch_tasks}

        skipped = []
        for stock in stocks:
            if stock["ticker"] not in analyzed_tickers:
                # Find the existing completed task for this ticker + date
                with self._get_conn() as conn:
                    row = conn.execute(
                        """SELECT task_id, status, signal, completed_at FROM tasks
                           WHERE ticker = ? AND trade_date = ? AND status = 'completed'
                           ORDER BY created_at DESC LIMIT 1""",
                        (stock["ticker"], trade_date),
                    ).fetchone()
                    if row:
                        skipped.append({
                            "ticker": stock["ticker"],
                            "name": stock["name"],
                            "reason": "已有今日分析结果",
                            "existing_task_id": row["task_id"],
                            "signal": row["signal"],
                            "completed_at": row["completed_at"],
                        })
        return skipped

    def recover_running_batches(self):
        """On startup, recover any batch_runs that were left in 'running' state."""
        with self._get_conn() as conn:
            batches = conn.execute(
                "SELECT batch_id FROM batch_runs WHERE status = 'running'"
            ).fetchall()

        for row in batches:
            batch_id = row["batch_id"]
            tasks = self.get_batch_tasks(batch_id)
            completed = sum(1 for t in tasks if t["status"] == "completed")
            failed = sum(1 for t in tasks if t["status"] in ("failed", "cancelled"))

            self.update_batch_task_count(batch_id, completed, failed)

            if completed + failed >= len(tasks) and len(tasks) > 0:
                if failed == 0:
                    status = "completed"
                elif completed == 0:
                    status = "failed"
                else:
                    status = "partial_failure"
                self.finish_batch_run(batch_id, status)
            else:
                # Still incomplete - mark as partial_failure since runner is gone
                self.finish_batch_run(batch_id, "partial_failure", error="服务重启，批量分析中断")
