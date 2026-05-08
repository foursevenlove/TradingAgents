"""Simple file-based cache for data source results."""
import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any, Dict
import threading


class DataCache:
    """File-based cache with TTL support for tool results."""

    def __init__(self, cache_dir: str = None, default_ttl_hours: int = 24):
        self._cache_dir = Path(cache_dir or os.getenv("TRADINGAGENTS_CACHE_DIR", "./data_cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl_hours = default_ttl_hours
        self._lock = threading.Lock()

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key."""
        # Use hash to avoid long filenames
        key_hash = hashlib.md5(key.encode()).hexdigest()[:16]
        return self._cache_dir / f"{key_hash}.json"

    def _build_key(self, tool_name: str, ticker: str, date: str = None, **kwargs) -> str:
        """Build cache key from tool name and parameters."""
        parts = [tool_name, ticker]
        if date:
            parts.append(date)
        # Add kwargs hash if present
        if kwargs:
            kwargs_hash = hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()[:8]
            parts.append(kwargs_hash)
        return ":".join(parts)

    def get(self, tool_name: str, ticker: str, date: str = None, **kwargs) -> Optional[Any]:
        """Get cached result if exists and not expired."""
        key = self._build_key(tool_name, ticker, date, **kwargs)
        cache_path = self._get_cache_path(key)

        with self._lock:
            if not cache_path.exists():
                return None

            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check TTL
                cached_at = datetime.fromisoformat(data.get("cached_at", ""))
                ttl_hours = data.get("ttl_hours", self._default_ttl_hours)
                if datetime.utcnow() > cached_at + timedelta(hours=ttl_hours):
                    return None

                return data.get("result")
            except (json.JSONDecodeError, ValueError, KeyError):
                return None

    def set(self, tool_name: str, ticker: str, result: Any, date: str = None, ttl_hours: int = None, **kwargs):
        """Cache a result with TTL."""
        key = self._build_key(tool_name, ticker, date, **kwargs)
        cache_path = self._get_cache_path(key)

        with self._lock:
            data = {
                "key": key,
                "tool_name": tool_name,
                "ticker": ticker,
                "date": date,
                "result": result,
                "cached_at": datetime.utcnow().isoformat(),
                "ttl_hours": ttl_hours or self._default_ttl_hours,
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def clear_expired(self):
        """Remove all expired cache entries."""
        with self._lock:
            for cache_file in self._cache_dir.glob("*.json"):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cached_at = datetime.fromisoformat(data.get("cached_at", ""))
                    ttl_hours = data.get("ttl_hours", self._default_ttl_hours)
                    if datetime.utcnow() > cached_at + timedelta(hours=ttl_hours):
                        cache_file.unlink()
                except (json.JSONDecodeError, ValueError, KeyError):
                    cache_file.unlink()  # Remove corrupted cache file

    def clear_all(self):
        """Remove all cache entries."""
        with self._lock:
            for cache_file in self._cache_dir.glob("*.json"):
                cache_file.unlink()


# Specialized caches with different TTLs

class IndustryCache(DataCache):
    """Cache for industry classification results (30 day TTL)."""

    def __init__(self, cache_dir: str = None):
        super().__init__(cache_dir, default_ttl_hours=30 * 24)  # 30 days

    def get_industry(self, ticker: str) -> Optional[Dict]:
        """Get cached industry classification."""
        return self.get("get_sw_industry", ticker)

    def set_industry(self, ticker: str, result: Dict):
        """Cache industry classification."""
        self.set("get_sw_industry", ticker, result)


class KeywordCache(DataCache):
    """Cache for LLM-generated keywords (30 day TTL)."""

    def __init__(self, cache_dir: str = None):
        super().__init__(cache_dir, default_ttl_hours=30 * 24)  # 30 days

    def get_keywords(self, ticker: str) -> Optional[list]:
        """Get cached keywords for a ticker."""
        return self.get("llm_keywords", ticker)

    def set_keywords(self, ticker: str, keywords: list):
        """Cache keywords for a ticker."""
        self.set("llm_keywords", ticker, keywords)


class ToolResultCache(DataCache):
    """Cache for tool results (daily TTL)."""

    def __init__(self, cache_dir: str = None):
        super().__init__(cache_dir, default_ttl_hours=24)  # 1 day

    def get_result(self, tool_name: str, ticker: str, trade_date: str) -> Optional[Any]:
        """Get cached tool result for a specific date."""
        return self.get(tool_name, ticker, trade_date)

    def set_result(self, tool_name: str, ticker: str, trade_date: str, result: Any):
        """Cache tool result for a specific date."""
        self.set(tool_name, ticker, result, trade_date)


# Global cache instances
_data_cache: Optional[ToolResultCache] = None
_industry_cache: Optional[IndustryCache] = None
_keyword_cache: Optional[KeywordCache] = None


def get_data_cache() -> ToolResultCache:
    """Get global tool result cache."""
    global _data_cache
    if _data_cache is None:
        cache_dir = os.path.join(os.path.dirname(__file__), "../dataflows/data_cache")
        _data_cache = ToolResultCache(cache_dir)
    return _data_cache


def get_industry_cache() -> IndustryCache:
    """Get global industry cache."""
    global _industry_cache
    if _industry_cache is None:
        cache_dir = os.path.join(os.path.dirname(__file__), "../dataflows/data_cache")
        _industry_cache = IndustryCache(cache_dir)
    return _industry_cache


def get_keyword_cache() -> KeywordCache:
    """Get global keyword cache."""
    global _keyword_cache
    if _keyword_cache is None:
        cache_dir = os.path.join(os.path.dirname(__file__), "../dataflows/data_cache")
        _keyword_cache = KeywordCache(cache_dir)
    return _keyword_cache