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

        # Get company information from cninfo (巨潮资讯)
        # More stable than eastmoney API
        df = ak.stock_profile_cninfo(symbol=stock_code)

        if df.empty:
            return f"No fundamental data found for {ticker}"

        # Transpose to make it more readable (columns become rows)
        df_transposed = df.T.reset_index()
        df_transposed.columns = ['Item', 'Value']

        # Format as CSV
        header = f"# Fundamental data for {ticker}\n"
        header += f"# Data source: cninfo (巨潮资讯)\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df_transposed, header)

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

        # Convert to Sina format (e.g., sh600667)
        sina_symbol = f"{market.lower()}{stock_code}"

        # Get balance sheet data from Sina
        df = ak.stock_financial_report_sina(stock=sina_symbol, symbol='资产负债表')

        if df.empty:
            return f"No balance sheet data found for {ticker}"

        header = f"# Balance sheet for {ticker} ({freq})\n"
        header += f"# Data source: Sina Finance\n"
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

        # Convert to Sina format (e.g., sh600667)
        sina_symbol = f"{market.lower()}{stock_code}"

        # Get cash flow data from Sina
        df = ak.stock_financial_report_sina(stock=sina_symbol, symbol='现金流量表')

        if df.empty:
            return f"No cash flow data found for {ticker}"

        header = f"# Cash flow statement for {ticker} ({freq})\n"
        header += f"# Data source: Sina Finance\n"
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

        # Convert to Sina format (e.g., sh600667)
        sina_symbol = f"{market.lower()}{stock_code}"

        # Get income statement data from Sina
        df = ak.stock_financial_report_sina(stock=sina_symbol, symbol='利润表')

        if df.empty:
            return f"No income statement data found for {ticker}"

        header = f"# Income statement for {ticker} ({freq})\n"
        header += f"# Data source: Sina Finance\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get income statement for {ticker}: {str(e)}")
