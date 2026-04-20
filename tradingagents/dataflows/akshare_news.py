"""Akshare news data implementation for A-share market."""

import re
from datetime import datetime
from typing import Annotated, Optional
import akshare as ak
import pandas as pd

from .akshare_common import _convert_ticker_format, _format_to_csv, AkshareDataError


def _parse_date_from_url(url: str) -> Optional[datetime]:
    """Extract date from East Money news URL.

    URLs like http://finance.eastmoney.com/a/202603163673069 contain
    the date as YYYYMMDD in the path.
    """
    if not url:
        return None
    match = re.search(r"/a/(\d{8})", url)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return None
    return None


def get_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Get news for specific A-share stock.

    Args:
        ticker: A-share ticker symbol
        start_date: Start date (optional, not used by akshare)
        end_date: End date (optional, not used by akshare)

    Returns:
        CSV string containing news data

    Note:
        akshare's stock_news_em doesn't support date filtering,
        so start_date and end_date are accepted but ignored for compatibility.
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get stock news from East Money
        # ak.stock_news_em expects format like "600176.SH" or "000001.SZ"
        # so we need to reconstruct the full symbol
        news_symbol = f"{stock_code}.{market.upper()}"
        df = ak.stock_news_em(symbol=news_symbol)

        if df.empty:
            return f"No news found for {ticker}"

        # Parse date from URL and sort by date descending to get newest first
        date_range_info = ""
        if "新闻链接" in df.columns:
            df["_parsed_date"] = df["新闻链接"].apply(_parse_date_from_url)
            # Drop rows where date parsing failed
            df = df.dropna(subset=["_parsed_date"])
            # Sort by parsed date descending (newest first)
            df = df.sort_values("_parsed_date", ascending=False)
            # Record date range before dropping helper column
            dates = df["_parsed_date"]
            if not dates.empty:
                date_range_info = f"# Date range: {dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}\n"
            # Drop the helper column before outputting
            df = df.drop(columns=["_parsed_date"])

        # Limit to top 20 most recent items
        df = df.head(20)

        header = f"# News for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(df)}\n"
        if date_range_info:
            header += date_range_info

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get news for {ticker}: {str(e)}")


def get_global_news(
    curr_date: Optional[str] = None,
    look_back_days: Optional[int] = None,
    limit: Optional[int] = None,
) -> str:
    """Get global financial news relevant to A-share market.

    Uses 财联社 (cls) financial news + 新闻联播 (CCTV) macro policy news.
    The former Baidu finance API (news_economic_baidu) has been discontinued.

    Args:
        curr_date: Current date (optional)
        look_back_days: Number of days to look back (optional)
        limit: Maximum number of news items to return (default: 20)

    Returns:
        CSV string containing global news data
    """
    try:
        all_news = []

        # Source 1: 财联社 (CLS) - real-time financial news feed
        try:
            df_cls = ak.stock_info_global_cls()
            if not df_cls.empty:
                # Rename columns to consistent format
                df_cls = df_cls.rename(columns={
                    "标题": "Title",
                    "内容": "Content",
                    "发布日期": "Date",
                    "发布时间": "Time",
                })
                all_news.append(df_cls)
        except Exception:
            pass  # CLS may be temporarily unavailable

        # Source 2: 新闻联播 (CCTV) - macro policy news, very important for A-share policy analysis
        if curr_date is not None:
            cctv_date = curr_date.replace("-", "")
            try:
                df_cctv = ak.news_cctv(date=cctv_date)
                if not df_cctv.empty:
                    df_cctv = df_cctv.rename(columns={
                        "date": "Date",
                        "title": "Title",
                        "content": "Content",
                    })
                    df_cctv["Source"] = "CCTV新闻联播"
                    all_news.append(df_cctv)
            except Exception:
                pass  # CCTV data may not be available for this date yet

        if not all_news:
            return "No global news available (CLS and CCTV sources temporarily unavailable)"

        df = pd.concat(all_news, ignore_index=True)

        # Limit output
        max_items = limit if limit is not None else 20
        df = df.head(max_items)

        header = f"# Global financial news (财联社 + 新闻联播)\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        return f"No global news available ({str(e)})"


def get_insider_transactions(
    ticker: Annotated[str, "A-share ticker symbol"],
) -> str:
    """Get insider transactions (shareholder changes) for A-share stocks.

    Args:
        ticker: A-share ticker symbol

    Returns:
        CSV string containing insider transaction data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get shareholder changes
        # ak.stock_zh_a_gdhs returns shareholder change data
        df = ak.stock_zh_a_gdhs(symbol=stock_code)

        if df.empty:
            return f"No insider transaction data found for {ticker}"

        header = f"# Insider transactions for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get insider transactions for {ticker}: {str(e)}")
