"""Common utilities for akshare data source."""

from datetime import datetime
import pandas as pd
from typing import Optional
import os

# 禁用代理，确保akshare直连访问东方财富网
# akshare访问的是中国大陆网站，不需要代理
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if proxy_var in os.environ:
        del os.environ[proxy_var]


def _convert_ticker_format(symbol: str) -> tuple[str, str]:
    """Convert ticker format to akshare format.

    Args:
        symbol: Ticker symbol (e.g., "000001.SZ", "600000.SH", "000001")

    Returns:
        Tuple of (stock_code, market) where:
        - stock_code: 6-digit code (e.g., "000001", "600000")
        - market: Market identifier ("sz" for Shenzhen, "sh" for Shanghai)

    Examples:
        "000001.SZ" -> ("000001", "sz")
        "600000.SH" -> ("600000", "sh")
        "000001" -> ("000001", "sz")  # Default to Shenzhen for 000xxx
        "600000" -> ("600000", "sh")  # Default to Shanghai for 600xxx
    """
    symbol = symbol.upper().strip()

    # Handle format with suffix (e.g., "000001.SZ")
    if "." in symbol:
        code, suffix = symbol.split(".")
        market = suffix.lower()
        return code, market

    # Handle format without suffix - infer from code
    # Shenzhen: 000xxx (main board), 002xxx (SME), 300xxx (ChiNext)
    # Shanghai: 600xxx, 601xxx, 603xxx, 688xxx (STAR)
    code = symbol
    if code.startswith(("000", "002", "300")):
        market = "sz"
    elif code.startswith(("600", "601", "603", "688")):
        market = "sh"
    else:
        # Default to Shenzhen for unknown patterns
        market = "sz"

    return code, market


def _filter_data_by_date_range(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    date_column: str = "日期"
) -> pd.DataFrame:
    """Filter DataFrame by date range.

    Args:
        df: DataFrame to filter
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format
        date_column: Name of the date column

    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df

    # Convert date column to datetime
    df[date_column] = pd.to_datetime(df[date_column])

    # Filter by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    filtered_df = df[(df[date_column] >= start_dt) & (df[date_column] <= end_dt)]

    return filtered_df


def _format_to_csv(df: pd.DataFrame, header_info: Optional[str] = None) -> str:
    """Format DataFrame to CSV string with optional header.

    Args:
        df: DataFrame to format
        header_info: Optional header information to prepend

    Returns:
        CSV string
    """
    if df.empty:
        if header_info:
            return header_info + "\nNo data available"
        return "No data available"

    csv_string = df.to_csv(index=False)

    if header_info:
        return header_info + "\n" + csv_string

    return csv_string


class AkshareDataError(Exception):
    """Exception raised for akshare data errors."""
    pass
