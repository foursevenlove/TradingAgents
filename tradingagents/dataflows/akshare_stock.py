"""Akshare stock data implementation for A-share market."""

from datetime import datetime
from typing import Annotated
import akshare as ak
import pandas as pd

from .akshare_common import (
    _convert_ticker_format,
    _filter_data_by_date_range,
    _format_to_csv,
    AkshareDataError,
)


def get_stock(
    symbol: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Get A-share stock OHLCV data from akshare.

    Args:
        symbol: A-share ticker symbol (e.g., "000001.SZ", "600000.SH")
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string containing daily OHLCV data

    Examples:
        >>> get_stock("000001.SZ", "2024-01-01", "2024-01-31")
        # Returns CSV with columns: Date, Open, High, Low, Close, Volume, etc.
    """
    try:
        # Validate date format
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")

        # Convert ticker format
        stock_code, market = _convert_ticker_format(symbol)

        # Fetch data from akshare using Tencent data source (more stable)
        # stock_zh_a_hist_tx uses Tencent API instead of eastmoney push2his API
        # Format: sh600000 for Shanghai, sz000001 for Shenzhen
        tx_symbol = f"{market}{stock_code}"
        df = ak.stock_zh_a_hist_tx(
            symbol=tx_symbol,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )

        if df.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        # Rename columns to match expected format
        # Tencent data source columns: date, open, close, high, low, amount
        column_mapping = {
            "date": "Date",
            "open": "Open",
            "close": "Close",
            "high": "High",
            "low": "Low",
            "amount": "Volume",  # Tencent uses 'amount' for volume
        }

        # Select and rename relevant columns
        available_cols = [col for col in column_mapping.keys() if col in df.columns]
        df_selected = df[available_cols].copy()
        df_selected.rename(columns=column_mapping, inplace=True)

        # Round numerical values
        numeric_columns = ["Open", "High", "Low", "Close"]
        for col in numeric_columns:
            if col in df_selected.columns:
                df_selected[col] = df_selected[col].round(2)

        # Add header information
        header = f"# A-share stock data for {symbol} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(df_selected)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Market: {'Shenzhen' if market == 'sz' else 'Shanghai'}\n"

        return _format_to_csv(df_selected, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to fetch stock data for {symbol}: {str(e)}")
