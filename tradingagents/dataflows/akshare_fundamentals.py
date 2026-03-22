"""Akshare fundamentals data implementation for A-share market."""

from datetime import datetime
from typing import Annotated, Optional
import akshare as ak
import pandas as pd

from .akshare_common import _convert_ticker_format, _format_to_csv, AkshareDataError


def get_fundamentals(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Get company fundamental information for A-share stocks.

    Args:
        ticker: A-share ticker symbol
        curr_date: Current date (optional, for consistency with interface)

    Returns:
        CSV string containing company fundamental data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get company information
        # ak.stock_individual_info_em returns basic company info
        df = ak.stock_individual_info_em(symbol=stock_code)

        if df.empty:
            return f"No fundamental data found for {ticker}"

        # Format as CSV
        header = f"# Fundamental data for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get fundamentals for {ticker}: {str(e)}")


def get_balance_sheet(
    ticker: Annotated[str, "A-share ticker symbol"],
    freq: Annotated[str, "Frequency: quarterly or annual"] = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    """Get balance sheet data for A-share stocks.

    Args:
        ticker: A-share ticker symbol
        freq: Frequency (quarterly or annual)
        curr_date: Current date (optional)

    Returns:
        CSV string containing balance sheet data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get balance sheet data
        # ak.stock_balance_sheet_by_report_em returns balance sheet
        df = ak.stock_balance_sheet_by_report_em(symbol=stock_code)

        if df.empty:
            return f"No balance sheet data found for {ticker}"

        header = f"# Balance sheet for {ticker} ({freq})\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get balance sheet for {ticker}: {str(e)}")


def get_cashflow(
    ticker: Annotated[str, "A-share ticker symbol"],
    freq: Annotated[str, "Frequency: quarterly or annual"] = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    """Get cash flow statement for A-share stocks.

    Args:
        ticker: A-share ticker symbol
        freq: Frequency (quarterly or annual)
        curr_date: Current date (optional)

    Returns:
        CSV string containing cash flow data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get cash flow data
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=stock_code)

        if df.empty:
            return f"No cash flow data found for {ticker}"

        header = f"# Cash flow statement for {ticker} ({freq})\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get cash flow for {ticker}: {str(e)}")


def get_income_statement(
    ticker: Annotated[str, "A-share ticker symbol"],
    freq: Annotated[str, "Frequency: quarterly or annual"] = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    """Get income statement for A-share stocks.

    Args:
        ticker: A-share ticker symbol
        freq: Frequency (quarterly or annual)
        curr_date: Current date (optional)

    Returns:
        CSV string containing income statement data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get income statement data
        df = ak.stock_profit_sheet_by_report_em(symbol=stock_code)

        if df.empty:
            return f"No income statement data found for {ticker}"

        header = f"# Income statement for {ticker} ({freq})\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get income statement for {ticker}: {str(e)}")
