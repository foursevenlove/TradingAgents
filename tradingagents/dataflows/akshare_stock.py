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

        # Try multiple stable data sources (avoid eastmoney APIs)
        stock_code, market = _convert_ticker_format(symbol)
        tx_symbol = f"{market}{stock_code}"
        df = None
        error_msgs = []

        # Try 1: Tencent API (most stable for stocks)
        try:
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            if df is not None and not df.empty:
                source = "Tencent"
        except Exception as e:
            error_msgs.append(f"Tencent: {str(e)[:50]}")

        # Try 2: Sina API (good for ETFs and stocks)
        if df is None or df.empty:
            try:
                df = ak.fund_etf_hist_sina(symbol=stock_code)
                if df is not None and not df.empty:
                    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
                    source = "Sina"
            except Exception as e:
                error_msgs.append(f"Sina: {str(e)[:50]}")

        # Try 3: 163 API (NetEase, another stable source)
        if df is None or df.empty:
            try:
                df = ak.stock_zh_a_hist_163(
                    symbol=stock_code,
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                )
                if df is not None and not df.empty:
                    source = "163"
            except Exception as e:
                error_msgs.append(f"163: {str(e)[:50]}")

        if df is None or df.empty:
            error_detail = "; ".join(error_msgs) if error_msgs else "All sources failed"
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}. Errors: {error_detail}"

        # Rename columns to match expected format
        column_mapping = {
            "date": "Date",
            "日期": "Date",
            "open": "Open",
            "开盘": "Open",
            "close": "Close",
            "收盘": "Close",
            "high": "High",
            "最高": "High",
            "low": "Low",
            "最低": "Low",
            "amount": "Volume",
            "成交量": "Volume",
        }

        # Select and rename relevant columns
        available_cols = [col for col in column_mapping.keys() if col in df.columns]
        if not available_cols:
            return f"Unexpected data format for symbol '{symbol}'"

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
