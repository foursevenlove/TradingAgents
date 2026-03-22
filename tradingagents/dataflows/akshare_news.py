"""Akshare news data implementation for A-share market."""

from datetime import datetime
from typing import Annotated, Optional
import akshare as ak
import pandas as pd

from .akshare_common import _convert_ticker_format, _format_to_csv, AkshareDataError


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
        # ak.stock_news_em returns recent news for the stock
        df = ak.stock_news_em(symbol=stock_code)

        if df.empty:
            return f"No news found for {ticker}"

        # Limit to recent news (e.g., last 20 items)
        df = df.head(20)

        header = f"# News for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get news for {ticker}: {str(e)}")


def get_global_news(
    curr_date: Optional[str] = None,
    look_back_days: Optional[int] = None,
    limit: Optional[int] = None,
) -> str:
    """Get global financial news relevant to A-share market.

    Args:
        curr_date: Current date (optional, not used by akshare)
        look_back_days: Number of days to look back (optional, not used by akshare)
        limit: Maximum number of news items to return (default: 30)

    Returns:
        CSV string containing global news data

    Note:
        akshare's news_economic_baidu doesn't support date filtering,
        so curr_date and look_back_days are accepted but ignored for compatibility.
    """
    try:
        # Get financial news
        # ak.news_economic_baidu returns economic news
        df = ak.news_economic_baidu()

        if df.empty:
            return "No global news available"

        # Limit to recent news
        max_items = limit if limit is not None else 30
        df = df.head(max_items)

        header = f"# Global financial news\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get global news: {str(e)}")


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
