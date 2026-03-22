"""Akshare technical indicators implementation for A-share market."""

from datetime import datetime, timedelta
from typing import Annotated
import akshare as ak
import pandas as pd

from .akshare_common import _convert_ticker_format, AkshareDataError
from .stockstats_utils import StockstatsUtils


def get_indicator(
    symbol: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    indicator: Annotated[str, "Technical indicator name (e.g., macd, rsi, boll)"],
    curr_date: Annotated[str, "Current trading date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"],
) -> str:
    """Get technical indicator data for A-share stocks.

    This function reuses the stockstats library to calculate indicators,
    similar to yfinance implementation, but fetches data from akshare.

    Args:
        symbol: A-share ticker symbol
        indicator: Technical indicator name
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back

    Returns:
        CSV string containing indicator data
    """
    try:
        # Validate date format
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        # Calculate start date
        start_dt = curr_dt - timedelta(days=look_back_days + 200)  # Extra buffer for calculation
        start_date = start_dt.strftime("%Y-%m-%d")

        # Convert ticker format
        stock_code, market = _convert_ticker_format(symbol)

        # Fetch historical data from akshare
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=curr_date.replace("-", ""),
            adjust="qfq",
        )

        if df.empty:
            return f"No data found for symbol '{symbol}'"

        # Rename columns to match stockstats format
        # stockstats expects: date, open, high, low, close, volume
        column_mapping = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        }

        df_renamed = df.rename(columns=column_mapping)

        # Use StockstatsUtils to calculate indicator
        stats_util = StockstatsUtils()
        result_df = stats_util.get_indicator(df_renamed, indicator)

        if result_df.empty:
            return f"Failed to calculate indicator '{indicator}' for {symbol}"

        # Filter to requested date range
        result_df["date"] = pd.to_datetime(result_df["date"])
        filter_start = curr_dt - timedelta(days=look_back_days)
        result_df = result_df[result_df["date"] >= filter_start]

        # Add header
        header = f"# Technical indicator '{indicator}' for {symbol}\n"
        header += f"# Date range: {filter_start.strftime('%Y-%m-%d')} to {curr_date}\n"
        header += f"# Total records: {len(result_df)}\n"

        csv_string = result_df.to_csv(index=False)
        return header + "\n" + csv_string

    except Exception as e:
        raise AkshareDataError(f"Failed to get indicator {indicator} for {symbol}: {str(e)}")
