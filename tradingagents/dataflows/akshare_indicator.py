"""Akshare technical indicators implementation for A-share market."""

from datetime import datetime, timedelta
from typing import Annotated
import warnings
import akshare as ak
import pandas as pd
from stockstats import wrap

from .akshare_common import _convert_ticker_format, AkshareDataError


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

        # Try multiple stable data sources (avoid eastmoney APIs)
        stock_code, market = _convert_ticker_format(symbol)
        tx_symbol = f"{market}{stock_code}"
        df = None

        # Try 1: Tencent API
        try:
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol,
                start_date=start_date.replace("-", ""),
                end_date=curr_date.replace("-", ""),
            )
        except Exception:
            pass

        # Try 2: Sina API
        if df is None or df.empty:
            try:
                df = ak.fund_etf_hist_sina(symbol=stock_code)
                if df is not None and not df.empty:
                    df = df[(df['date'] >= start_date) & (df['date'] <= curr_date)]
            except Exception:
                pass

        # Try 3: 163 API
        if df is None or df.empty:
            try:
                df = ak.stock_zh_a_hist_163(
                    symbol=stock_code,
                    start_date=start_date.replace("-", ""),
                    end_date=curr_date.replace("-", ""),
                )
            except Exception:
                pass

        if df is None or df.empty:
            return f"No data found for symbol '{symbol}'"

        # Rename columns to match stockstats format
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
            "volume": "Volume",
            "成交量": "Volume",
        }

        df_renamed = df.rename(columns=column_mapping)

        # Ensure required columns exist
        required = ["Date", "Open", "High", "Low", "Close"]
        if not all(col in df_renamed.columns for col in required):
            return f"Missing required price data for symbol '{symbol}'"

        # Use stockstats to calculate indicator
        # Wrap the dataframe with stockstats
        stock_df = wrap(df_renamed)

        # Map indicator names to stockstats column names
        # stockstats uses: boll_ub (upper), boll_lb (lower), boll_mid (middle)
        indicator_mapping = {
            "boll_upper": "boll_ub",
            "boll_lower": "boll_lb",
            "boll_mid": "boll_mid",
            "boll_up": "boll_ub",
            "boll_down": "boll_lb",
        }
        mapped_indicator = indicator_mapping.get(indicator, indicator)

        # Handle boll indicators specially - stockstats generates boll_lb, boll_mid, boll_ub
        # when accessing 'boll', so we need to calculate 'boll' first, then access the specific column
        if mapped_indicator in ("boll_ub", "boll_lb", "boll_mid"):
            stock_df["boll"]  # Calculate all boll columns first
        else:
            # Calculate the indicator (this triggers stockstats calculation)
            # Some indicators like volume_ratio may raise UserWarning in stockstats or fail to calculate.
            # Catch any failure (Exception or UserWarning) and return a graceful error.
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", UserWarning)  # Turn warnings into exceptions
                    stock_df[mapped_indicator]
            except (Exception, UserWarning) as e:
                return f"Unsupported indicator '{indicator}' for {symbol}"

        # Select relevant columns for output (use mapped_indicator to get actual column name)
        output_cols = ["Date", "Open", "High", "Low", "Close", "Volume", mapped_indicator]
        available_cols = [col for col in output_cols if col in stock_df.columns]
        result_df = stock_df[available_cols].copy()

        if result_df.empty or mapped_indicator not in result_df.columns:
            return f"Unsupported indicator '{indicator}' for {symbol}"

        # Filter to requested date range
        result_df["Date"] = pd.to_datetime(result_df["Date"])
        filter_start = curr_dt - timedelta(days=look_back_days)
        result_df = result_df[result_df["Date"] >= filter_start]

        # Add header
        header = f"# Technical indicator '{indicator}' for {symbol}\n"
        header += f"# Date range: {filter_start.strftime('%Y-%m-%d')} to {curr_date}\n"
        header += f"# Total records: {len(result_df)}\n"

        csv_string = result_df.to_csv(index=False)
        return header + "\n" + csv_string

    except Exception as e:
        raise AkshareDataError(f"Failed to get indicator {indicator} for {symbol}: {str(e)}")
