"""Stock search service with cached stock list."""
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import sqlite3
import threading

# Get db path directly from environment
_BASE_DIR = Path(__file__).parent.parent
DB_PATH = os.getenv("TRADINGAGENTS_WEB_DB", str(_BASE_DIR / "tasks.db"))

# Global cache for stock list
_stock_cache: List[Dict[str, str]] = []
_cache_loaded = False
_cache_loading = False
_cache_lock = threading.Lock()
_cache_time: Optional[datetime] = None
logger = logging.getLogger("tradingagents.web.stock_service")


def _convert_akshare_code_to_tushare(code: str) -> str:
    """Convert akshare code 'sh600176' to tushare format '600176.SH'."""
    code = code.strip().lower()
    if code.startswith('sh'):
        return f"{code[2:]}.SH"
    elif code.startswith('sz'):
        return f"{code[2:]}.SZ"
    elif code.startswith('bj'):
        return f"{code[2:]}.BJ"
    return code.upper()


def _load_stock_cache():
    """Load stock list from akshare and cache it."""
    global _stock_cache, _cache_loaded, _cache_time

    try:
        import akshare as ak
        df = ak.stock_zh_a_spot()
        stocks = []
        for _, row in df.iterrows():
            ak_code = str(row['代码']).strip()
            name = str(row['名称']).strip()
            # Convert akshare format (sh600176) to tushare format (600176.SH)
            ticker = _convert_akshare_code_to_tushare(ak_code)
            # Extract numeric code (600176)
            numeric_code = ticker.split('.')[0] if '.' in ticker else ticker
            stocks.append({
                'ticker': ticker,
                'code': numeric_code,
                'ak_code': ak_code,  # Keep original for matching
                'name': name,
            })
        _stock_cache = stocks
        _cache_loaded = True
        _cache_time = datetime.utcnow()
        # Also save to database for fallback
        _save_stock_list_to_db(stocks)
        return True
    except Exception as e:
        logger.warning(
            "Failed to load stock cache from akshare, trying database fallback",
            exc_info=(type(e), e, e.__traceback__),
            extra={"extra_data": {"stage": "stock_cache_load_akshare"}},
        )
        # Try to load from database
        _stock_cache = _load_stock_list_from_db()
        if _stock_cache:
            _cache_loaded = True
            _cache_time = datetime.utcnow()
            logger.info(
                "Loaded stock cache from database fallback",
                extra={"extra_data": {
                    "stage": "stock_cache_load_db",
                    "stock_count": len(_stock_cache),
                }},
            )
            return True
        logger.error(
            "Stock cache load failed and database fallback is empty",
            extra={"extra_data": {"stage": "stock_cache_load_failed"}},
        )
        return False


def _save_stock_list_to_db(stocks: List[Dict[str, str]]):
    """Save stock list to database for fallback."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        # Create table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_list (
                ticker TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # Clear and insert
        now = datetime.utcnow().isoformat() + "Z"
        conn.execute("DELETE FROM stock_list")
        for stock in stocks:
            conn.execute(
                "INSERT OR REPLACE INTO stock_list (ticker, code, name, updated_at) VALUES (?, ?, ?, ?)",
                (stock['ticker'], stock['code'], stock['name'], now)
            )
        conn.commit()


def _load_stock_list_from_db() -> List[Dict[str, str]]:
    """Load stock list from database."""
    db_path = Path(DB_PATH)
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT ticker, code, name FROM stock_list").fetchall()
        return [{'ticker': r['ticker'], 'code': r['code'], 'name': r['name']} for r in rows]


def get_stock_list() -> List[Dict[str, str]]:
    """Get cached stock list, loading if necessary."""
    global _cache_loaded, _cache_loading

    with _cache_lock:
        if not _cache_loaded and not _cache_loading:
            _cache_loading = True
            success = _load_stock_cache()
            _cache_loading = False
            if not success:
                return []

    # Refresh cache if older than 1 day
    if _cache_time and (datetime.utcnow() - _cache_time).days >= 1:
        threading.Thread(target=_load_stock_cache, daemon=True).start()

    return _stock_cache


def search_stocks(query: str, limit: int = 20) -> List[Dict[str, str]]:
    """Search stocks by code or name."""
    stocks = get_stock_list()
    if not stocks:
        return []

    query = query.strip().lower()
    results = []

    for stock in stocks:
        ticker = stock['ticker'].lower()
        code = stock['code'].lower()
        name = stock['name'].lower()

        # Match by ticker/code prefix (支持600176匹配600176.SH)
        if ticker.startswith(query) or code.startswith(query):
            results.append(stock)
        # Match by name contains
        elif query in name:
            results.append(stock)

        if len(results) >= limit:
            break

    return results


def get_stock_name(ticker: str) -> str:
    """Get stock name from cache."""
    stocks = get_stock_list()
    # Normalize ticker format
    ticker_upper = ticker.upper()
    for stock in stocks:
        if stock['ticker'] == ticker_upper or stock['code'] == ticker_upper:
            return stock['name']
    return ""
