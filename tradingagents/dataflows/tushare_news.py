"""Tushare Pro news data implementation.

Provides news data from Tushare Pro API, with multiple data source support
and intelligent filtering for stock-specific news.

Requires:
    - tushare package (pip install tushare)
    - TUSHARE_TOKEN environment variable (get from https://tushare.pro)
    - Separate permission for news/major_news/cctv_news interfaces
"""

import os
from datetime import datetime, timedelta
from typing import Annotated, Optional, List
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


def _get_stock_name_from_code(stock_code: str) -> Optional[str]:
    """Get stock name from stock code for keyword filtering.

    Uses tushare's stock_basic interface to get the company name.
    """
    try:
        pro = _get_pro_api()
        # Convert code to ts_code format
        ts_code = _convert_ticker_to_tushare(stock_code)
        df = pro.stock_basic(ts_code=ts_code, fields='ts_code,name')
        if not df.empty:
            return df.iloc[0]['name']
    except Exception:
        pass
    return None


def _format_to_csv(df: pd.DataFrame, header_info: Optional[str] = None) -> str:
    """Format DataFrame to CSV string with optional header."""
    if df.empty:
        return "No data available"

    csv_string = df.to_csv(index=False)

    if header_info:
        return header_info + "\n" + csv_string

    return csv_string


def _filter_by_keywords(df: pd.DataFrame, keywords: List[str]) -> pd.DataFrame:
    """Filter news DataFrame by keywords in title or content.

    Args:
        df: News DataFrame with 'title' and optionally 'content' columns
        keywords: List of keywords to search for (e.g., company name, stock code)

    Returns:
        Filtered DataFrame containing only rows matching any keyword
    """
    if df.empty or not keywords:
        return df

    # Build search pattern
    keywords_lower = [k.lower() for k in keywords]

    def matches_row(row):
        title = str(row.get('title', '')).lower()
        content = str(row.get('content', '')).lower()

        for keyword in keywords_lower:
            if keyword in title or keyword in content:
                return True
        return False

    # Filter rows
    mask = df.apply(matches_row, axis=1)
    filtered_df = df[mask]

    return filtered_df


def get_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """Get news for specific A-share stock using Tushare Pro.

    Strategy:
    1. Call tushare news API with multiple data sources (eastmoney, sina, 10jqka, cls, yicai, jinrongjie)
    2. Filter results by company name and stock code keywords
    3. If filtered results < 5, fallback to akshare stock_news_em (which supports stock code query)

    Args:
        ticker: A-share ticker symbol
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string containing filtered news data relevant to the stock
    """
    try:
        pro = _get_pro_api()
        stock_code = _convert_ticker_to_tushare(ticker)

        # Get company name for keyword filtering
        company_name = _get_stock_name_from_code(ticker)
        keywords = [stock_code.split('.')[0]]  # Stock code without market suffix
        if company_name:
            keywords.append(company_name)

        # Set default date range
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # Format dates for Tushare API (requires datetime format)
        start_dt = f"{start_date} 00:00:00"
        end_dt = f"{end_date} 23:59:59"

        # Data sources for company-specific news (per user's specification)
        company_news_sources = ['eastmoney', 'sina', '10jqka', 'cls', 'yicai', 'jinrongjie']

        all_news = []

        # Collect news from each source
        for src in company_news_sources:
            try:
                df = pro.news(src=src, start_date=start_dt, end_date=end_dt)
                if not df.empty:
                    # Add source identifier
                    df['data_source'] = src
                    all_news.append(df)
            except Exception:
                # Some sources may be temporarily unavailable, continue with others
                continue

        # Merge all news
        if all_news:
            merged_df = pd.concat(all_news, ignore_index=True)
            # Deduplicate by title
            merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')

            # Filter by keywords
            filtered_df = _filter_by_keywords(merged_df, keywords)

            # Check if we have enough filtered results
            min_required = 20
            if len(filtered_df) < min_required:
                # Try major_news as additional source (may have more content)
                try:
                    major_df = pro.major_news(
                        src='',
                        start_date=start_dt,
                        end_date=end_dt,
                        fields='title,content,pub_time,src'
                    )
                    if not major_df.empty:
                        # Rename columns to match news format
                        major_df = major_df.rename(columns={'pub_time': 'datetime', 'src': 'data_source'})
                        major_df['data_source'] = 'major_news_' + major_df['data_source'].astype(str)

                        # Merge and filter
                        merged_with_major = pd.concat([merged_df, major_df], ignore_index=True)
                        merged_with_major = merged_with_major.drop_duplicates(subset=['title'], keep='first')
                        filtered_df = _filter_by_keywords(merged_with_major, keywords)
                except Exception:
                    pass

            # If still not enough, prepare for akshare fallback (done by route_to_vendor)
            if len(filtered_df) < min_required:
                # Return partial results with fallback marker
                # route_to_vendor will combine with akshare data
                if filtered_df.empty:
                    header = f"# Tushare News for {ticker}\n"
                    header += f"# Company name: {company_name or 'N/A'}\n"
                    header += f"# Date range: {start_date} to {end_date}\n"
                    header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    header += f"# NOTE: No stock-specific news found via Tushare keyword filter.\n"
                    header += f"# Keywords used: {keywords}\n"
                    header += f"# Total raw news collected: {len(merged_df)}\n"
                    header += f"# Filtered results: 0 (will fallback to akshare)\n"
                    return header + "\n_FALLBACK_TO_AKSHARE_"
                else:
                    # Return partial tushare results + fallback marker
                    filtered_df = filtered_df.head(50)
                    header = f"# Tushare News for {ticker} (partial results)\n"
                    header += f"# Company name: {company_name or 'N/A'}\n"
                    header += f"# Date range: {start_date} to {end_date}\n"
                    header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    header += f"# Keywords used for filtering: {keywords}\n"
                    header += f"# Total raw news collected: {len(merged_df)}\n"
                    header += f"# Filtered results: {len(filtered_df)} (< {min_required}, will supplement with akshare)\n"
                    header += f"# Data sources: {', '.join(company_news_sources)}\n"
                    return _format_to_csv(filtered_df, header) + "\n_FALLBACK_TO_AKSHARE_"
            else:
                # Sort by datetime descending (newest first)
                if 'datetime' in filtered_df.columns:
                    filtered_df = filtered_df.sort_values('datetime', ascending=False)
                elif 'pub_time' in filtered_df.columns:
                    filtered_df = filtered_df.sort_values('pub_time', ascending=False)

                # Limit to top 20
                filtered_df = filtered_df.head(50)

            header = f"# Tushare News for {ticker}\n"
            header += f"# Company name: {company_name or 'N/A'}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# Keywords used for filtering: {keywords}\n"
            header += f"# Total raw news collected: {len(merged_df) if all_news else 0}\n"
            header += f"# Filtered results: {len(filtered_df)}\n"
            header += f"# Data sources: {', '.join(company_news_sources)}\n"

            return _format_to_csv(filtered_df, header)

        else:
            # No news from tushare, trigger akshare fallback
            header = f"# Tushare News for {ticker}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# NOTE: Tushare returned no news, falling back to akshare.\n"
            return header + "\n_FALLBACK_TO_AKSHARE_"

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare news for {ticker}: {str(e)}")


def get_global_news(
    curr_date: Annotated[str, "当前日期，格式：yyyy-mm-dd"] = None,
    look_back_days: Annotated[int, "回溯天数"] = 7,
    limit: Annotated[int, "返回的最大文章数"] = 200,
) -> str:
    """Get global financial news using Tushare Pro.

    Strategy:
    1. Call tushare news API with global-focused sources (wallstreetcn, yuncaijing)
    2. Fallback/supplement with akshare (cls + cctv)

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

        # Data sources for global/macro news (per user's specification)
        global_news_sources = ['wallstreetcn', 'yuncaijing']

        all_news = []

        for src in global_news_sources:
            try:
                df = pro.news(src=src, start_date=start_str, end_date=end_str)
                if not df.empty:
                    df['data_source'] = src
                    all_news.append(df)
            except Exception:
                continue

        if all_news:
            merged_df = pd.concat(all_news, ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')

            # Sort by datetime descending
            if 'datetime' in merged_df.columns:
                merged_df = merged_df.sort_values('datetime', ascending=False)

            # Limit output
            merged_df = merged_df.head(limit)

            header = f"# Tushare Global Financial News\n"
            header += f"# Date range: {start_dt.strftime('%Y-%m-%d')} to {curr_date}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# Total items: {len(merged_df)}\n"
            header += f"# Data sources: {', '.join(global_news_sources)}\n"

            return _format_to_csv(merged_df, header)

        else:
            # Trigger akshare fallback
            header = f"# Tushare Global Financial News\n"
            header += f"# Date range: {start_dt.strftime('%Y-%m-%d')} to {curr_date}\n"
            header += f"# NOTE: Tushare returned no news, falling back to akshare.\n"
            return header + "\n_FALLBACK_TO_AKSHARE_"

    except TushareDataError as e:
        raise e
    except Exception as e:
        return f"Tushare global news unavailable: {str(e)}"


def get_cctv_news(
    look_back_days: Annotated[int, "回溯天数，默认3天"] = 3,
) -> str:
    """Get CCTV news broadcast text transcripts using Tushare Pro.

    Provides official policy announcements and macro economic policy content,
    which is essential for A-share policy market analysis.

    Args:
        look_back_days: Number of days to look back (default: 3 days)

    Returns:
        CSV string containing CCTV news broadcast transcripts
    """
    try:
        pro = _get_pro_api()

        # Get news for recent days
        all_cctv = []
        today = datetime.now()

        for i in range(look_back_days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")

            try:
                df = pro.cctv_news(date=date_str)
                if not df.empty:
                    df['retrieved_date'] = date.strftime("%Y-%m-%d")
                    all_cctv.append(df)
            except Exception:
                # Some dates may not have data yet (e.g., today's broadcast not uploaded)
                continue

        if all_cctv:
            merged_df = pd.concat(all_cctv, ignore_index=True)

            header = f"# CCTV News Broadcast Transcripts (新闻联播文字稿)\n"
            header += f"# Date range: {(today - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# Total segments: {len(merged_df)}\n"
            header += f"# Note: Official policy announcements for macro analysis\n"

            return _format_to_csv(merged_df, header)

        else:
            return f"No CCTV news broadcast data available for the past {look_back_days} days"

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get CCTV news: {str(e)}")


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