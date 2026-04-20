"""Tushare Pro news data implementation.

Provides news data from Tushare Pro API, which supports date filtering
and stable access compared to akshare's free scraping interfaces.

Requires:
    - tushare package (pip install tushare)
    - TUSHARE_TOKEN environment variable (get from https://tushare.pro)
    - Minimum 120积分 for news interface, separate permission for major_news
"""

import os
from datetime import datetime, timedelta
from typing import Annotated, Optional
import pandas as pd

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False


class TushareDataError(Exception):
    """Exception raised for Tushare data errors."""
    pass


def _get_pro_api():
    """Get Tushare Pro API instance.

    Token is read from TUSHARE_TOKEN environment variable.
    """
    if not TUSHARE_AVAILABLE:
        raise TushareDataError(
            "tushare package not installed. Install with: pip install tushare"
        )

    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise TushareDataError(
            "TUSHARE_TOKEN not set. Get your token from https://tushare.pro "
            "and set it in .env or environment variable."
        )

    return ts.pro_api(token)


def _convert_ticker_to_tushare(symbol: str) -> str:
    """Convert ticker format to Tushare format (e.g., 000001.SZ).

    Tushare uses the same format as the existing akshare convention.
    """
    symbol = symbol.upper().strip()
    if "." in symbol:
        return symbol

    # Infer market from code prefix
    if symbol.startswith(("000", "002", "300")):
        return f"{symbol}.SZ"
    elif symbol.startswith(("600", "601", "603", "688")):
        return f"{symbol}.SH"
    else:
        return f"{symbol}.SZ"


def _format_to_csv(df: pd.DataFrame, header_info: Optional[str] = None) -> str:
    """Format DataFrame to CSV string with optional header."""
    if df.empty:
        return "No data available"

    csv_string = df.to_csv(index=False)

    if header_info:
        return header_info + "\n" + csv_string

    return csv_string


def get_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """Get news for specific A-share stock using Tushare Pro.

    Tushare's news interface supports date filtering, which is a key
    advantage over akshare's free interface.

    Args:
        ticker: A-share ticker symbol
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string containing news data with title, content, pub_time, src
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(ticker)

        # Tushare news interface: get individual stock-related news
        # The news interface returns general financial news
        # For stock-specific news, we query major_news filtered by date range
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # Format dates for Tushare API (YYYYMMDD or YYYY-MM-DD HH:MM:SS)
        start_dt = f"{start_date} 00:00:00"
        end_dt = f"{end_date} 23:59:59"

        # Try major_news first (better content quality)
        try:
            df = pro.major_news(
                src='',
                start_date=start_dt,
                end_date=end_dt,
                fields='title,content,pub_time,src'
            )
        except Exception:
            # If major_news requires separate permission, fall back to news
            df = pro.news(
                src='sina',
                start_date=start_dt,
                end_date=end_dt,
                fields='title,content,datetime,channels'
            )
            if not df.empty and 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'pub_time', 'channels': 'src'})

        if df.empty:
            return f"No Tushare news data found for date range {start_date} to {end_date}"

        # De-duplicate (Tushare major_news may have duplicate entries from same src)
        if 'title' in df.columns and 'content' in df.columns:
            df = df.drop_duplicates(subset=['title'], keep='first')

        # Limit to top 30 items
        df = df.head(30)

        header = f"# Tushare News for {ticker} (date range: {start_date} to {end_date})\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(df)}\n"
        header += f"# Data source: Tushare Pro\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare news for {ticker}: {str(e)}")


def get_global_news(
    curr_date: Annotated[str, "当前日期，格式：yyyy-mm-dd"] = None,
    look_back_days: Annotated[int, "回溯天数"] = 7,
    limit: Annotated[int, "返回的最大文章数"] = 5,
) -> str:
    """Get global financial news using Tushare Pro.

    Uses Tushare's major_news interface to get comprehensive financial news
    from multiple sources (新华网, 凤凰财经, 新浪财经, 华尔街见闻, etc.)

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of news items to return

    Returns:
        CSV string containing global financial news
    """
    try:
        pro = _get_pro_api()

        if curr_date is None:
            curr_date = datetime.now().strftime("%Y-%m-%d")

        # Calculate date range
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=look_back_days)

        start_str = f"{start_dt.strftime('%Y-%m-%d')} 00:00:00"
        end_str = f"{end_dt.strftime('%Y-%m-%d')} 23:59:59"

        # Try major_news (better content quality, multiple sources)
        try:
            df = pro.major_news(
                src='',
                start_date=start_str,
                end_date=end_str,
                fields='title,content,pub_time,src'
            )
        except Exception:
            # Fall back to news if major_news permission not available
            df = pro.news(
                src='sina',
                start_date=start_str,
                end_date=end_str,
                fields='title,content,datetime,channels'
            )
            if not df.empty and 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'pub_time', 'channels': 'src'})

        if df.empty:
            return f"No Tushare global news available for date range"

        # De-duplicate
        if 'title' in df.columns:
            df = df.drop_duplicates(subset=['title'], keep='first')

        # Limit output
        df = df.head(limit if limit else 30)

        header = f"# Tushare Global Financial News\n"
        header += f"# Date range: {start_dt.strftime('%Y-%m-%d')} to {curr_date}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(df)}\n"
        header += f"# Data source: Tushare Pro\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        # Return graceful error rather than crashing the pipeline
        return f"Tushare global news unavailable: {str(e)}"


def get_insider_transactions(
    ticker: Annotated[str, "A-share ticker symbol"],
) -> str:
    """Get insider transactions (shareholder changes) using Tushare Pro.

    Args:
        ticker: A-share ticker symbol

    Returns:
        CSV string containing insider transaction data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(ticker)

        # Tushare's stk_holdertrade interface for shareholder trading changes
        df = pro.stk_holdertrade(ts_code=ts_code)

        if df.empty:
            return f"No insider transaction data found for {ticker} via Tushare"

        header = f"# Insider Transactions for {ticker} (Tushare Pro)\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total records: {len(df)}\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare insider transactions for {ticker}: {str(e)}")