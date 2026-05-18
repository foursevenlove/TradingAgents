"""News Cache Manager - Local 30-day news cache with background updates.

Architecture:
- SQLite database for structured storage
- Background thread for hourly updates
- Three-layer storage: structured + original + summary
- Auto cleanup of old data (30-day retention)
"""

import os
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

from tradingagents.recommendation.news_parsing import parse_recommendation_news_csv

# Cache directory
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DB_PATH = CACHE_DIR / "news_cache.db"
logger = logging.getLogger("tradingagents.web.recommendation.news_cache")

# Retention period
RETENTION_DAYS = 30

# Update interval (seconds)
UPDATE_INTERVAL = 3600  # 1 hour


class NewsCacheManager:
    """Manage local news cache with SQLite backend."""

    def __init__(self):
        self._ensure_cache_dir()
        self._init_database()
        self._update_thread = None
        self._running = False

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with Row factory."""
        conn = sqlite3.connect(str(CACHE_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize SQLite tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # News table (three-layer storage)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id TEXT UNIQUE,
                title TEXT NOT NULL,
                datetime TEXT NOT NULL,
                source TEXT,
                structured TEXT,          -- JSON: key_entities, related_industries, event_type, importance, sentiment, keywords
                content_original TEXT,    -- Full original content
                content_summary TEXT,     -- LLM-generated summary (100 chars)
                processed_at TEXT,        -- When LLM preprocessing was done
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_datetime
            ON news(datetime)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_processed
            ON news(processed_at)
        """)

        # Theme history table (keyword-based tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS theme_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                keywords_hash TEXT NOT NULL,
                keywords TEXT NOT NULL,   -- JSON list of keywords
                theme_name TEXT,
                confidence REAL,
                news_count INTEGER,
                consecutive_days INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_theme_date
            ON theme_history(date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_theme_hash
            ON theme_history(keywords_hash)
        """)

        # Update log table (track background updates)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS update_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                update_time TEXT NOT NULL,
                news_added INTEGER,
                news_processed INTEGER,
                status TEXT,
                error_message TEXT
            )
        """)

        conn.commit()
        conn.close()

    # ── Background Update ────────────────────────────────────────────────

    def start_background_update(self):
        """Start background update thread."""
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(
            target=self._background_update_loop,
            daemon=True,
        )
        self._update_thread.start()
        logger.info("News cache background update thread started")

    def stop_background_update(self):
        """Stop background update thread."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5)
        logger.info("News cache background update thread stopped")

    def _background_update_loop(self):
        """Background loop: fetch and process news periodically."""
        # Initial update on startup
        self._do_update()

        while self._running:
            # Wait for next update interval
            time.sleep(UPDATE_INTERVAL)

            if not self._running:
                break

            # Do periodic update
            self._do_update()

    def _do_update(self):
        """Perform one update cycle: fetch -> process -> store."""
        from tradingagents.dataflows.interface import route_to_vendor

        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        news_added = 0
        news_processed = 0
        status = "success"
        error_message = ""

        try:
            # 1. Fetch latest news (look_back_days=1 for hourly update)
            logger.info(
                "News cache update started",
                extra={"extra_data": {
                    "stage": "news_cache_fetch",
                    "update_time": update_time,
                }},
            )
            raw_news_csv = route_to_vendor(
                "get_recommendation_news",
                look_back_days=1,
                max_articles=500,
            )

            # 2. Parse CSV to list
            news_list = self._parse_csv_to_list(raw_news_csv)
            logger.info(
                "News cache fetched news items",
                extra={"extra_data": {
                    "stage": "news_cache_fetch",
                    "news_count": len(news_list),
                }},
            )

            # 3. Store raw news (unprocessed)
            for news in news_list:
                if self._store_raw_news(news):
                    news_added += 1

            logger.info(
                "News cache stored raw news items",
                extra={"extra_data": {
                    "stage": "news_cache_store_raw",
                    "news_added": news_added,
                }},
            )

            # 4. Process unprocessed news with LLM
            unprocessed = self._get_unprocessed_news(limit=100)
            if unprocessed:
                from tradingagents.recommendation.news_preprocessor import NewsPreprocessor
                preprocessor = NewsPreprocessor()

                for news in unprocessed[:100]:  # Process batch of 100
                    try:
                        processed = preprocessor.process_news(news)
                        self._update_processed_news(news["news_id"], processed)
                        news_processed += 1
                    except Exception as e:
                        logger.error(
                            "News cache processing item failed",
                            exc_info=(type(e), e, e.__traceback__),
                            extra={"extra_data": {
                                "stage": "news_cache_process_item",
                                "news_id": news.get("news_id"),
                            }},
                        )
                        continue

                logger.info(
                    "News cache processed news items",
                    extra={"extra_data": {
                        "stage": "news_cache_process",
                        "news_processed": news_processed,
                    }},
                )

            # 5. Cleanup old data
            self._cleanup_old_data()

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(
                "News cache update failed",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {
                    "stage": "news_cache_update",
                    "update_time": update_time,
                }},
            )

        # 6. Log update
        self._log_update(update_time, news_added, news_processed, status, error_message)

    # ── News Storage ──────────────────────────────────────────────────────

    def _parse_csv_to_list(self, csv_string: str) -> List[Dict]:
        """Parse CSV string to list of news dicts."""
        news_list = []
        for row in parse_recommendation_news_csv(csv_string):
            datetime_str = row.get("datetime", "")
            if not datetime_str:
                # Use current time as fallback when datetime is missing
                datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            title = row.get("title", "")
            # Generate unique news_id from title hash + timestamp
            news_id = f"{datetime_str[:10]}_{hash(title) % 1000000:06d}"

            news_list.append({
                "news_id": news_id,
                "title": title,
                "datetime": datetime_str,
                "source": row.get("data_source", ""),
                "content_original": row.get("content", ""),
            })

        return news_list

    def _store_raw_news(self, news: Dict) -> bool:
        """Store raw news (before LLM processing). Returns True if new."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO news
                (news_id, title, datetime, source, content_original)
                VALUES (?, ?, ?, ?, ?)
            """, (
                news["news_id"],
                news["title"],
                news["datetime"],
                news["source"],
                news["content_original"],
            ))

            conn.commit()
            inserted = cursor.rowcount > 0
            return inserted

        finally:
            conn.close()

    def _get_unprocessed_news(self, limit: int = 100) -> List[Dict]:
        """Get news items that haven't been processed by LLM."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT news_id, title, datetime, source, content_original
                FROM news
                WHERE processed_at IS NULL
                ORDER BY datetime DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        finally:
            conn.close()

    def _update_processed_news(self, news_id: str, processed: Dict):
        """Update news with LLM processed data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE news
                SET structured = ?, content_summary = ?, processed_at = ?
                WHERE news_id = ?
            """, (
                json.dumps(processed["structured"], ensure_ascii=False),
                processed["content_summary"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                news_id,
            ))

            conn.commit()

        finally:
            conn.close()

    # ── News Retrieval ────────────────────────────────────────────────────

    def get_news_for_theme_extraction(
        self,
        start_date: str,
        end_date: str,
        min_importance: float = 0.3,
    ) -> List[Dict]:
        """Get processed news for theme extraction (Phase 1).

        Returns news with structured info, filtered by importance.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT news_id, title, datetime, source, structured, content_summary
                FROM news
                WHERE datetime >= ? AND datetime <= ?
                  AND processed_at IS NOT NULL
                  AND json_extract(structured, '$.importance') >= ?
                ORDER BY datetime DESC
            """, (start_date, end_date + " 23:59:59", min_importance))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                structured = json.loads(row["structured"]) if row["structured"] else {}
                results.append({
                    "news_id": row["news_id"],
                    "title": row["title"],
                    "datetime": row["datetime"],
                    "source": row["source"],
                    "structured": structured,
                    "content_summary": row["content_summary"],
                })

            return results

        finally:
            conn.close()

    def get_news_for_deep_analysis(
        self,
        keywords: List[str],
        limit: int = 10,
    ) -> List[Dict]:
        """Get news with original content for deep analysis (Phase 4).

        Used by News Analyst when analyzing a specific stock.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build keyword search pattern
            keyword_pattern = " OR ".join([f"title LIKE '%{kw}%'" for kw in keywords])

            cursor.execute(f"""
                SELECT news_id, title, datetime, source, content_original, structured
                FROM news
                WHERE processed_at IS NOT NULL
                  AND ({keyword_pattern})
                ORDER BY datetime DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                structured = json.loads(row["structured"]) if row["structured"] else {}
                results.append({
                    "news_id": row["news_id"],
                    "title": row["title"],
                    "datetime": row["datetime"],
                    "source": row["source"],
                    "content_original": row["content_original"],
                    "structured": structured,
                })

            return results

        finally:
            conn.close()

    def get_recent_news(
        self,
        days: int = 7,
        limit: int = 500,
    ) -> List[Dict]:
        """Get recent news (all processed, with structured info)."""
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        return self.get_news_for_theme_extraction(start_date, end_date)

    # ── Cleanup ───────────────────────────────────────────────────────────

    def _cleanup_old_data(self):
        """Remove news older than RETENTION_DAYS."""
        cutoff_date = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Delete old news
            cursor.execute("""
                DELETE FROM news WHERE datetime < ?
            """, (cutoff_date,))
            deleted_news = cursor.rowcount

            # Delete old theme history
            cursor.execute("""
                DELETE FROM theme_history WHERE date < ?
            """, (cutoff_date,))
            deleted_themes = cursor.rowcount

            conn.commit()

            if deleted_news > 0 or deleted_themes > 0:
                logger.info(
                    "News cache cleanup removed old rows",
                    extra={"extra_data": {
                        "stage": "news_cache_cleanup",
                        "deleted_news": deleted_news,
                        "deleted_themes": deleted_themes,
                    }},
                )

        finally:
            conn.close()

    # ── Logging ───────────────────────────────────────────────────────────

    def _log_update(
        self,
        update_time: str,
        news_added: int,
        news_processed: int,
        status: str,
        error_message: str,
    ):
        """Log update to database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO update_log
                (update_time, news_added, news_processed, status, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (update_time, news_added, news_processed, status, error_message))

            conn.commit()

        finally:
            conn.close()

    def get_last_update_status(self) -> Optional[Dict]:
        """Get last update log entry."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM update_log
                ORDER BY update_time DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None

        finally:
            conn.close()

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Count total news
            cursor.execute("SELECT COUNT(*) FROM news")
            total_news = cursor.fetchone()[0]

            # Count processed news
            cursor.execute("SELECT COUNT(*) FROM news WHERE processed_at IS NOT NULL")
            processed_news = cursor.fetchone()[0]

            # Count theme history
            cursor.execute("SELECT COUNT(*) FROM theme_history")
            total_themes = cursor.fetchone()[0]

            # Get date range
            cursor.execute("SELECT MIN(datetime), MAX(datetime) FROM news")
            date_range = cursor.fetchone()

            return {
                "total_news": total_news,
                "processed_news": processed_news,
                "unprocessed_news": total_news - processed_news,
                "total_themes": total_themes,
                "date_range": {
                    "start": date_range[0] if date_range[0] else None,
                    "end": date_range[1] if date_range[1] else None,
                },
                "last_update": self.get_last_update_status(),
            }

        finally:
            conn.close()


# Singleton instance
_cache_manager: Optional[NewsCacheManager] = None


def get_cache_manager() -> NewsCacheManager:
    """Get singleton NewsCacheManager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = NewsCacheManager()
    return _cache_manager
