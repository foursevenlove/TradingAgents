"""Task manager with in-memory tracking and SQLite persistence."""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock

from .models import TaskStatus, TaskSummary, TaskDetail
from .config import WEB_CONFIG


class TaskManager:
    """Manages analysis task lifecycle."""

    def __init__(self):
        self._tasks: Dict[str, dict] = {}
        self._locks: Dict[str, Lock] = {}
        self._db_path = Path(WEB_CONFIG["db_path"])
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    signal TEXT,
                    result TEXT,
                    config TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
                """
            )
            conn.commit()

    def create_task(self, ticker: str, trade_date: str, config: dict) -> str:
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        task = {
            "task_id": task_id,
            "ticker": ticker,
            "trade_date": trade_date,
            "status": TaskStatus.PENDING.value,
            "created_at": now,
            "completed_at": None,
            "error": None,
            "signal": None,
            "result": None,
            "config": config,
        }
        self._tasks[task_id] = task
        self._locks[task_id] = Lock()

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task_id,
                    ticker,
                    trade_date,
                    task["status"],
                    now,
                    None,
                    None,
                    None,
                    None,
                    json.dumps(config, ensure_ascii=False),
                ),
            )
            conn.commit()
        return task_id

    def get_lock(self, task_id: str) -> Lock:
        return self._locks.get(task_id, Lock())

    def update_status(self, task_id: str, status: TaskStatus, error: Optional[str] = None):
        if task_id not in self._tasks:
            return
        self._tasks[task_id]["status"] = status.value
        if error:
            self._tasks[task_id]["error"] = error
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self._tasks[task_id]["completed_at"] = datetime.utcnow().isoformat() + "Z"

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, error = ?, completed_at = ? WHERE task_id = ?",
                (
                    status.value,
                    error,
                    self._tasks[task_id]["completed_at"],
                    task_id,
                ),
            )
            conn.commit()

    def set_result(self, task_id: str, result: dict, signal: str):
        if task_id not in self._tasks:
            return
        self._tasks[task_id]["result"] = result
        self._tasks[task_id]["signal"] = signal

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE tasks SET result = ?, signal = ? WHERE task_id = ?",
                (
                    json.dumps(result, ensure_ascii=False),
                    signal,
                    task_id,
                ),
            )
            conn.commit()

    def save_event(self, task_id: str, event_type: str, data: dict):
        now = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO events (task_id, event_type, timestamp, data) VALUES (?, ?, ?, ?)",
                (task_id, event_type, now, json.dumps(data, ensure_ascii=False)),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[dict]:
        # First check in-memory
        if task_id in self._tasks:
            return self._tasks[task_id]
        # Fallback to database for tasks created in previous server instances
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row:
                task = dict(row)
                # Parse JSON fields that were stored as strings
                for key in ("result", "config"):
                    if task.get(key) and isinstance(task[key], str):
                        try:
                            task[key] = json.loads(task[key])
                        except Exception:
                            pass
                return task
        return None

    def get_task_from_db(self, task_id: str) -> Optional[TaskDetail]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None

            events = conn.execute(
                "SELECT event_type, timestamp, data FROM events WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()

        return TaskDetail(
            task_id=row["task_id"],
            ticker=row["ticker"],
            trade_date=row["trade_date"],
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            error=row["error"],
            result=json.loads(row["result"]) if row["result"] else None,
            events=[
                {
                    "type": e["event_type"],
                    "timestamp": e["timestamp"],
                    "data": json.loads(e["data"]),
                }
                for e in events
            ],
        )

    def list_tasks(self, limit: int = 50, offset: int = 0) -> List[TaskSummary]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT task_id, ticker, trade_date, status, created_at, completed_at, error, signal
                FROM tasks
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        return [
            TaskSummary(
                task_id=r["task_id"],
                ticker=r["ticker"],
                trade_date=r["trade_date"],
                status=TaskStatus(r["status"]),
                created_at=datetime.fromisoformat(r["created_at"]),
                completed_at=datetime.fromisoformat(r["completed_at"]) if r["completed_at"] else None,
                error=r["error"],
                signal=r["signal"],
            )
            for r in rows
        ]

    def get_total_count(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
            return row[0] if row else 0


# Global instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
