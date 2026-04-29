"""Portfolio holdings CRUD."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import WEB_CONFIG


class HoldingsManager:
    """Manages user's stock holdings."""

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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT UNIQUE NOT NULL,
                    name TEXT DEFAULT '',
                    quantity INTEGER NOT NULL DEFAULT 0,
                    cost_price REAL NOT NULL DEFAULT 0.0,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def list_holdings(self) -> List[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM holdings ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_holding(
        self,
        ticker: str,
        name: str = "",
        quantity: int = 0,
        cost_price: float = 0.0,
        notes: str = "",
    ) -> dict:
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO holdings (ticker, name, quantity, cost_price, notes, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ticker, name, quantity, cost_price, notes, now, now),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                conn.execute(
                    "UPDATE holdings SET name = ?, quantity = ?, cost_price = ?, notes = ?, updated_at = ? "
                    "WHERE ticker = ?",
                    (name, quantity, cost_price, notes, now, ticker),
                )
                conn.commit()
            row = conn.execute(
                "SELECT * FROM holdings WHERE ticker = ?", (ticker,)
            ).fetchone()
        return dict(row)

    def update_holding(
        self,
        holding_id: int,
        quantity: int,
        cost_price: float,
        notes: str = "",
    ) -> bool:
        now = datetime.utcnow().isoformat() + "Z"
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE holdings SET quantity = ?, cost_price = ?, notes = ?, updated_at = ? WHERE id = ?",
                (quantity, cost_price, notes, now, holding_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def remove_holding(self, holding_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
            conn.commit()
        return cur.rowcount > 0

    def get_holding_by_ticker(self, ticker: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM holdings WHERE ticker = ?", (ticker,)
            ).fetchone()
        return dict(row) if row else None


def format_holdings_for_prompt(holding: Optional[dict]) -> str:
    if not holding:
        return "当前无持仓（空仓），这是一个全新的投资决策。"
    return (
        f"当前持仓信息：\n"
        f"- 股票：{holding['ticker']} {holding['name']}\n"
        f"- 持仓数量：{holding['quantity']}股\n"
        f"- 成本价：{holding['cost_price']}元\n"
        f"- 备注：{holding.get('notes', '') or '无'}"
    )
