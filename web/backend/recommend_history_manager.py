"""Recommendation History Manager - Persist recommendation results."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List


class RecommendHistoryManager:
    """Manage recommendation history persistence."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to web backend directory
            base_dir = Path(__file__).parent.parent.parent
            db_path = str(base_dir / "web" / "backend" / "recommend_history.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommend_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,           -- 'daily', 'weekly', 'top'
                trade_date TEXT NOT NULL,     -- 交易日期或周起始日期
                result_json TEXT NOT NULL,    -- JSON格式的推荐结果
                created_at TEXT NOT NULL,     -- 创建时间
                UNIQUE(mode, trade_date)      -- 每种模式每天只保存一条
            )
        """)
        conn.commit()
        conn.close()

    def save_result(self, mode: str, trade_date: str, result: Dict) -> bool:
        """Save recommendation result to database.

        Args:
            mode: 'daily', 'weekly', or 'top'
            trade_date: Trade date (YYYY-MM-DD)
            result: Full recommendation result dict

        Returns:
            True if saved successfully
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Add timestamp if not present
            if "saved_at" not in result:
                result["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            result_json = json.dumps(result, ensure_ascii=False)
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Upsert: insert or replace existing
            conn.execute("""
                INSERT OR REPLACE INTO recommend_history
                (mode, trade_date, result_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (mode, trade_date, result_json, created_at))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving recommendation: {e}")
            return False
        finally:
            conn.close()

    def get_latest_result(self, mode: str) -> Optional[Dict]:
        """Get the latest recommendation result for a mode.

        Args:
            mode: 'daily', 'weekly', or 'top'

        Returns:
            Dict with result data or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT mode, trade_date, result_json, created_at
                FROM recommend_history
                WHERE mode = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (mode,))

            row = cursor.fetchone()
            if row:
                return {
                    "mode": row[0],
                    "trade_date": row[1],
                    "result": json.loads(row[2]),
                    "created_at": row[3],
                }
            return None
        except Exception as e:
            print(f"Error getting recommendation: {e}")
            return None
        finally:
            conn.close()

    def get_result_by_date(self, mode: str, trade_date: str) -> Optional[Dict]:
        """Get recommendation result for specific date.

        Args:
            mode: 'daily', 'weekly', or 'top'
            trade_date: Trade date (YYYY-MM-DD)

        Returns:
            Dict with result data or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT mode, trade_date, result_json, created_at
                FROM recommend_history
                WHERE mode = ? AND trade_date = ?
            """, (mode, trade_date))

            row = cursor.fetchone()
            if row:
                return {
                    "mode": row[0],
                    "trade_date": row[1],
                    "result": json.loads(row[2]),
                    "created_at": row[3],
                }
            return None
        except Exception as e:
            print(f"Error getting recommendation: {e}")
            return None
        finally:
            conn.close()

    def list_history(self, mode: str = None, limit: int = 10) -> List[Dict]:
        """List recommendation history.

        Args:
            mode: Filter by mode (optional)
            limit: Maximum number of records

        Returns:
            List of history records
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if mode:
                cursor = conn.execute("""
                    SELECT mode, trade_date, created_at
                    FROM recommend_history
                    WHERE mode = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (mode, limit))
            else:
                cursor = conn.execute("""
                    SELECT mode, trade_date, created_at
                    FROM recommend_history
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "mode": row[0],
                    "trade_date": row[1],
                    "created_at": row[2],
                })
            return results
        except Exception as e:
            print(f"Error listing history: {e}")
            return []
        finally:
            conn.close()

    def clear_old_history(self, days: int = 30):
        """Clear history older than specified days.

        Args:
            days: Number of days to keep
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                DELETE FROM recommend_history
                WHERE created_at < ?
            """, (cutoff_str,))
            conn.commit()
        except Exception as e:
            print(f"Error clearing history: {e}")
        finally:
            conn.close()


# Singleton instance
_history_manager = None


def get_history_manager() -> RecommendHistoryManager:
    """Get singleton history manager instance."""
    global _history_manager
    if _history_manager is None:
        _history_manager = RecommendHistoryManager()
    return _history_manager