"""Theme Tracker - Track themes across days using keyword combination.

Key concept: Track themes by keyword combination, not by theme name.

- Same theme may have different names on different days
- But keyword combination is more stable for tracking
- Calculate consecutive days, identify new hotspots
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set

from tradingagents.recommendation.news_cache_manager import get_cache_manager


class ThemeTracker:
    """Track themes by keyword combination across days."""

    # Minimum keyword intersection to consider same theme
    KEYWORD_MATCH_THRESHOLD = 2

    # Days to look back for continuity
    CONTINUITY_LOOKBACK_DAYS = 7

    def __init__(self):
        self.cache_manager = get_cache_manager()

    def generate_keywords_hash(self, keywords: List[str]) -> str:
        """Generate hash for keyword combination.

        Used for exact matching in database.
        """
        # Sort and dedupe keywords
        sorted_keywords = sorted(set(keywords))
        keywords_str = ",".join(sorted_keywords)
        return hashlib.md5(keywords_str.encode()).hexdigest()[:12]

    def keywords_similarity(self, keywords1: List[str], keywords2: List[str]) -> int:
        """Calculate number of common keywords between two sets."""
        set1 = set(kw.lower() for kw in keywords1)
        set2 = set(kw.lower() for kw in keywords2)
        return len(set1 & set2)

    def is_same_theme(self, keywords1: List[str], keywords2: List[str]) -> bool:
        """Check if two keyword combinations represent same theme."""
        return self.keywords_similarity(keywords1, keywords2) >= self.KEYWORD_MATCH_THRESHOLD

    def track_theme(
        self,
        theme_name: str,
        keywords: List[str],
        confidence: float,
        news_count: int,
        date: str,
    ) -> Dict:
        """Track a theme and calculate continuity.

        Args:
            theme_name: LLM-generated theme name
            keywords: Keywords for this theme
            confidence: Confidence score
            news_count: Number of related news
            date: Current date (YYYY-MM-DD)

        Returns:
            Dict with continuity info: consecutive_days, trend, is_new_hotspot
        """
        keywords_hash = self.generate_keywords_hash(keywords)

        # Check exact match in history
        exact_history = self._get_exact_history(keywords_hash)

        if exact_history:
            # Found exact match - increment consecutive days
            consecutive_days = exact_history.get("consecutive_days", 1) + 1

            # Update existing record
            self._update_theme_history(
                keywords_hash=keywords_hash,
                date=date,
                theme_name=theme_name,
                confidence=confidence,
                news_count=news_count,
                consecutive_days=consecutive_days,
            )

            return {
                "consecutive_days": consecutive_days,
                "trend": "持续热点" if consecutive_days >= 3 else "新趋势",
                "is_new_hotspot": False,
                "keywords_hash": keywords_hash,
            }

        # No exact match - check fuzzy match (keyword similarity)
        fuzzy_match = self._find_fuzzy_match(keywords, date)

        if fuzzy_match:
            # Found similar theme - inherit continuity
            prev_consecutive = fuzzy_match.get("consecutive_days", 1)
            consecutive_days = prev_consecutive + 1

            # Create new record (different keywords, but related)
            self._save_theme_history(
                keywords_hash=keywords_hash,
                keywords=keywords,
                date=date,
                theme_name=theme_name,
                confidence=confidence,
                news_count=news_count,
                consecutive_days=consecutive_days,
            )

            return {
                "consecutive_days": consecutive_days,
                "trend": "持续热点" if consecutive_days >= 3 else "演变趋势",
                "is_new_hotspot": False,
                "keywords_hash": keywords_hash,
                "related_to": fuzzy_match.get("keywords_hash"),
            }

        # No match found - this is a new hotspot
        self._save_theme_history(
            keywords_hash=keywords_hash,
            keywords=keywords,
            date=date,
            theme_name=theme_name,
            confidence=confidence,
            news_count=news_count,
            consecutive_days=1,
        )

        return {
            "consecutive_days": 1,
            "trend": "新热点",
            "is_new_hotspot": True,
            "keywords_hash": keywords_hash,
        }

    def _get_exact_history(self, keywords_hash: str) -> Optional[Dict]:
        """Get theme history by exact hash match (from recent days)."""
        conn = self.cache_manager._get_connection()
        cursor = conn.cursor()

        try:
            # Look back 7 days
            start_date = (datetime.now() - timedelta(days=self.CONTINUITY_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT keywords_hash, keywords, theme_name, consecutive_days, date
                FROM theme_history
                WHERE keywords_hash = ? AND date >= ?
                ORDER BY date DESC
                LIMIT 1
            """, (keywords_hash, start_date))

            row = cursor.fetchone()
            if row:
                return {
                    "keywords_hash": row["keywords_hash"],
                    "keywords": json.loads(row["keywords"]),
                    "theme_name": row["theme_name"],
                    "consecutive_days": row["consecutive_days"],
                    "date": row["date"],
                }
            return None

        finally:
            conn.close()

    def _find_fuzzy_match(self, keywords: List[str], current_date: str) -> Optional[Dict]:
        """Find similar theme by keyword intersection (fuzzy match)."""
        conn = self.cache_manager._get_connection()
        cursor = conn.cursor()

        try:
            # Look back 7 days, exclude today
            start_date = (datetime.now() - timedelta(days=self.CONTINUITY_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT keywords_hash, keywords, theme_name, consecutive_days, date
                FROM theme_history
                WHERE date >= ? AND date < ?
                ORDER BY date DESC
            """, (start_date, current_date))

            rows = cursor.fetchall()

            for row in rows:
                history_keywords = json.loads(row["keywords"])
                similarity = self.keywords_similarity(keywords, history_keywords)

                if similarity >= self.KEYWORD_MATCH_THRESHOLD:
                    return {
                        "keywords_hash": row["keywords_hash"],
                        "keywords": history_keywords,
                        "theme_name": row["theme_name"],
                        "consecutive_days": row["consecutive_days"],
                        "date": row["date"],
                    }

            return None

        finally:
            conn.close()

    def _save_theme_history(
        self,
        keywords_hash: str,
        keywords: List[str],
        date: str,
        theme_name: str,
        confidence: float,
        news_count: int,
        consecutive_days: int,
    ):
        """Save new theme history record."""
        conn = self.cache_manager._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO theme_history
                (keywords_hash, keywords, date, theme_name, confidence, news_count, consecutive_days)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                keywords_hash,
                json.dumps(keywords, ensure_ascii=False),
                date,
                theme_name,
                confidence,
                news_count,
                consecutive_days,
            ))

            conn.commit()

        finally:
            conn.close()

    def _update_theme_history(
        self,
        keywords_hash: str,
        date: str,
        theme_name: str,
        confidence: float,
        news_count: int,
        consecutive_days: int,
    ):
        """Update existing theme history (increment consecutive days)."""
        conn = self.cache_manager._get_connection()
        cursor = conn.cursor()

        try:
            # Insert new record for today (same hash)
            cursor.execute("""
                INSERT OR REPLACE INTO theme_history
                (keywords_hash, date, theme_name, confidence, news_count, consecutive_days, keywords)
                VALUES (?, ?, ?, ?, ?, ?, (
                    SELECT keywords FROM theme_history
                    WHERE keywords_hash = ?
                    ORDER BY date DESC LIMIT 1
                ))
            """, (
                keywords_hash,
                date,
                theme_name,
                confidence,
                news_count,
                consecutive_days,
                keywords_hash,
            ))

            conn.commit()

        finally:
            conn.close()

    # ── Analytics ─────────────────────────────────────────────────────────

    def get_trending_themes(self, days: int = 7, min_consecutive: int = 2) -> List[Dict]:
        """Get themes that are trending (multiple consecutive days)."""
        conn = self.cache_manager._get_connection()
        cursor = conn.cursor()

        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT keywords_hash, keywords, theme_name,
                       MAX(consecutive_days) as max_consecutive,
                       COUNT(*) as appearance_days,
                       AVG(confidence) as avg_confidence,
                       SUM(news_count) as total_news
                FROM theme_history
                WHERE date >= ?
                GROUP BY keywords_hash
                HAVING max_consecutive >= ?
                ORDER BY max_consecutive DESC, avg_confidence DESC
            """, (start_date, min_consecutive))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "keywords_hash": row["keywords_hash"],
                    "keywords": json.loads(row["keywords"]),
                    "theme_name": row["theme_name"],
                    "consecutive_days": row["max_consecutive"],
                    "appearance_days": row["appearance_days"],
                    "avg_confidence": round(row["avg_confidence"], 2),
                    "total_news": row["total_news"],
                })

            return results

        finally:
            conn.close()

    def get_new_hotspots(self, date: str) -> List[Dict]:
        """Get themes that appeared as new hotspots on a specific date."""
        conn = self.cache_manager._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT keywords_hash, keywords, theme_name, confidence, news_count
                FROM theme_history
                WHERE date = ? AND consecutive_days = 1
                ORDER BY confidence DESC
            """, (date,))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "keywords_hash": row["keywords_hash"],
                    "keywords": json.loads(row["keywords"]),
                    "theme_name": row["theme_name"],
                    "confidence": row["confidence"],
                    "news_count": row["news_count"],
                })

            return results

        finally:
            conn.close()

    def get_theme_evolution(self, keywords_hash: str, days: int = 30) -> List[Dict]:
        """Get evolution of a theme over time."""
        conn = self.cache_manager._get_connection()
        cursor = conn.cursor()

        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT date, theme_name, confidence, news_count, consecutive_days
                FROM theme_history
                WHERE keywords_hash = ? AND date >= ?
                ORDER BY date ASC
            """, (keywords_hash, start_date))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "date": row["date"],
                    "theme_name": row["theme_name"],
                    "confidence": row["confidence"],
                    "news_count": row["news_count"],
                    "consecutive_days": row["consecutive_days"],
                })

            return results

        finally:
            conn.close()

    # ── Batch Tracking ─────────────────────────────────────────────────────

    def track_all_themes(self, themes: List[Dict], date: str) -> List[Dict]:
        """Track multiple themes and add continuity info.

        Args:
            themes: List of theme dicts from ThemeExtractor
            date: Current date

        Returns:
            List of themes with added continuity info
        """
        tracked_themes = []

        for theme in themes:
            keywords = theme.get("keywords", [])
            theme_name = theme.get("name", "")
            confidence = theme.get("confidence", 0.5)
            news_count = theme.get("news_count", 0)

            # Track this theme
            tracking_info = self.track_theme(
                theme_name=theme_name,
                keywords=keywords,
                confidence=confidence,
                news_count=news_count,
                date=date,
            )

            # Add tracking info to theme
            enhanced_theme = {
                **theme,
                "consecutive_days": tracking_info["consecutive_days"],
                "trend": tracking_info["trend"],
                "is_new_hotspot": tracking_info["is_new_hotspot"],
                "keywords_hash": tracking_info.get("keywords_hash"),
            }

            # Boost confidence for persistent themes
            if tracking_info["consecutive_days"] >= 3:
                confidence_boost = 0.05 * min(tracking_info["consecutive_days"], 5)
                enhanced_theme["confidence"] = min(
                    confidence + confidence_boost,
                    0.95
                )
                enhanced_theme["confidence_boost"] = confidence_boost

            tracked_themes.append(enhanced_theme)

        return tracked_themes