"""Tushare Pro core stock data and fundamentals implementation.

Provides stable, date-filterable A-share data from Tushare Pro API.
Key advantages over akshare:
  - Stable API with SLA (not free scraping)
  - Date filtering on all queries
  - Consistent data format
  - Rate limits instead of random failures

Requires:
  - tushare package (pip install tushare)
  - TUSHARE_TOKEN environment variable
  - 120积分 minimum for daily行情, 2000积分 for fundamentals
"""

import os
from datetime import datetime, timedelta
from typing import Annotated, Optional
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
    """Get Tushare Pro API instance."""
    if not TUSHARE_AVAILABLE:
        raise TushareDataError("tushare package not installed. Install with: pip install tushare")

    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise TushareDataError(
            "TUSHARE_TOKEN not set. Get your token from https://tushare.pro "
            "and set it in .env or environment variable."
        )

    return ts.pro_api(token)


def _convert_ticker_to_tushare(symbol: str) -> str:
    """Convert ticker format to Tushare format (e.g., 000001.SZ)."""
    symbol = symbol.upper().strip()
    if "." in symbol:
        return symbol
    if symbol.startswith(("000", "002", "300")):
        return f"{symbol}.SZ"
    elif symbol.startswith(("600", "601", "603", "688")):
        return f"{symbol}.SH"
    else:
        return f"{symbol}.SZ"


def _format_to_csv(df: pd.DataFrame, header_info: Optional[str] = None) -> str:
    """Format DataFrame to CSV string with optional header."""
    if df.empty:
        return "No data available"
    csv_string = df.to_csv(index=False)
    if header_info:
        return header_info + "\n" + csv_string
    return csv_string


def get_stock(
    symbol: Annotated[str, "A-share ticker symbol"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """Get A-share stock OHLCV data from Tushare Pro.

    Uses Tushare's daily interface, which provides stable and
    date-filterable daily stock data.

    Args:
        symbol: A-share ticker symbol (e.g., "000001.SZ", "600000.SH")
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string containing daily OHLCV data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(symbol)

        # Tushare uses YYYYMMDD format
        start_dt = start_date.replace("-", "")
        end_dt = end_date.replace("-", "")

        df = pro.daily(
            ts_code=ts_code,
            start_date=start_dt,
            end_date=end_dt,
        )

        if df.empty:
            return f"No Tushare stock data found for {symbol} between {start_date} and {end_date}"

        # Rename columns to match existing format
        column_mapping = {
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "pre_close": "Pre_Close",
            "change": "Change",
            "pct_chg": "Pct_Chg",
            "vol": "Volume",
            "amount": "Amount",
        }
        df = df.rename(columns=column_mapping)

        # Sort by date ascending
        df = df.sort_values("Date", ascending=True)

        # Format Date column from YYYYMMDD to YYYY-MM-DD
        df["Date"] = df["Date"].apply(lambda x: f"{x[:4]}-{x[4:6]}-{x[6:8]}")

        # Round numerical values
        numeric_cols = ["Open", "High", "Low", "Close", "Pre_Close", "Change", "Pct_Chg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].round(2)

        # Convert volume from 手 to 股 (multiply by 100)
        if "Volume" in df.columns:
            df["Volume"] = df["Volume"] * 100

        # Convert amount from 千元 to 元 (multiply by 1000)
        if "Amount" in df.columns:
            df["Amount"] = df["Amount"] * 1000

        header = f"# A-share stock data for {symbol} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare Pro (daily)\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare stock data for {symbol}: {str(e)}")


def get_indicator(
    symbol: Annotated[str, "A-share ticker symbol"],
    indicator: Annotated[str, "技术指标名称"],
    curr_date: Annotated[str, "当前交易日期，格式：YYYY-mm-dd"],
    look_back_days: Annotated[int, "回溯天数"] = 30,
) -> str:
    """Get technical indicators from Tushare Pro.

    Uses Tushare's daily_basic interface for PE/PB/turnover, and
    computes MACD/RSI/Bollinger from OHLCV data locally using stockstats.

    Args:
        symbol: A-share ticker symbol
        indicator: Technical indicator name
        curr_date: Current trading date
        look_back_days: Number of days to look back

    Returns:
        CSV string containing indicator data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(symbol)

        # For indicators that need raw OHLCV + local calculation (MACD, RSI, Boll, etc.)
        # We get the stock data first, then use stockstats
        # For market-level indicators (PE, PB, turnover), we use daily_basic

        # Get stock data for local indicator calculation
        end_dt = curr_date.replace("-", "")
        start_dt = (datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days + 200)).strftime("%Y%m%d")

        df = pro.daily(
            ts_code=ts_code,
            start_date=start_dt,
            end_date=end_dt,
        )

        if df.empty:
            return f"No Tushare data available for {symbol} to compute {indicator}"

        # Use stockstats for local calculation (same approach as akshare_indicator)
        try:
            from stockstats import StockDataFrame
            df_local = df.rename(columns={
                "trade_date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "vol": "Volume",
            })
            df_local["Date"] = df_local["Date"].apply(lambda x: f"{x[:4]}-{x[4:6]}-{x[6:8]}")
            df_local = df_local.sort_values("Date", ascending=True)
            df_local["Volume"] = df_local["Volume"] * 100  # Convert 手 to 股

            stock = StockDataFrame.retype(df_local)

            # Calculate indicator
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                indicator_data = stock[indicator]

            # Create output DataFrame
            result_df = pd.DataFrame({
                "Date": df_local["Date"].values[-look_back_days:] if len(df_local) >= look_back_days else df_local["Date"].values,
                indicator: indicator_data.values[-look_back_days:] if len(indicator_data) >= look_back_days else indicator_data.values,
            })

            header = f"# Technical indicator: {indicator} for {symbol}\n"
            header += f"# Date range: up to {curr_date}, look back {look_back_days} days\n"
            header += f"# Total records: {len(result_df)}\n"
            header += f"# Data source: Tushare Pro + stockstats local calculation\n"

            return _format_to_csv(result_df, header)

        except ImportError:
            raise TushareDataError("stockstats package not installed. Install with: pip install stockstats")

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare indicator {indicator} for {symbol}: {str(e)}")


def get_fundamentals(
    ticker: Annotated[str, "A-share ticker symbol"],
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """Get company fundamental information from Tushare Pro.

    Uses daily_basic for daily PE/PB/turnover/market_cap data.

    Args:
        ticker: A-share ticker symbol
        curr_date: Current date

    Returns:
        CSV string containing fundamental data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(ticker)

        if curr_date is None:
            curr_date = datetime.now().strftime("%Y-%m-%d")

        trade_date = curr_date.replace("-", "")

        # daily_basic provides PE, PB, turnover, market cap etc.
        # Requires 2000积分
        df = pro.daily_basic(
            ts_code=ts_code,
            trade_date=trade_date,
            fields='ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv'
        )

        if df.empty:
            return f"No Tushare fundamental data found for {ticker} on {curr_date}"

        # Rename columns
        column_mapping = {
            "ts_code": "Ticker",
            "trade_date": "Date",
            "close": "Close",
            "turnover_rate": "Turnover_Rate",
            "turnover_rate_f": "Turnover_Rate_Free",
            "volume": "Volume",
            "pe": "PE",
            "pe_ttm": "PE_TTM",
            "pb": "PB",
            "ps": "PS",
            "ps_ttm": "PS_TTM",
            "dv_ratio": "Dividend_Ratio",
            "dv_ttm": "Dividend_TTM",
            "total_share": "Total_Shares",
            "float_share": "Float_Shares",
            "free_share": "Free_Shares",
            "total_mv": "Total_Market_Cap",
            "circ_mv": "Circ_Market_Cap",
        }
        df = df.rename(columns=column_mapping)
        df["Date"] = df["Date"].apply(lambda x: f"{x[:4]}-{x[4:6]}-{x[6:8]}")

        header = f"# Tushare fundamental data for {ticker} on {curr_date}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare Pro (daily_basic)\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare fundamentals for {ticker}: {str(e)}")


def get_balance_sheet(
    ticker: Annotated[str, "A-share ticker symbol"],
    freq: Annotated[str, "报告频率：annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期"] = None,
) -> str:
    """Get balance sheet data from Tushare Pro.

    Args:
        ticker: A-share ticker symbol
        freq: Report frequency (annual/quarterly)
        curr_date: Current date

    Returns:
        CSV string containing balance sheet data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(ticker)

        # Get most recent balance sheet data
        # Tushare's balancesheet interface requires 2000积分
        if freq == "annual":
            report_type = "1"
        else:
            report_type = "2"

        df = pro.balancesheet(
            ts_code=ts_code,
            type=report_type,
        )

        if df.empty:
            return f"No Tushare balance sheet data found for {ticker}"

        # Limit to most recent 4 reports
        df = df.head(4)

        header = f"# Tushare balance sheet for {ticker}\n"
        header += f"# Report type: {freq}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare Pro\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare balance sheet for {ticker}: {str(e)}")


def get_cashflow(
    ticker: Annotated[str, "A-share ticker symbol"],
    freq: Annotated[str, "报告频率：annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期"] = None,
) -> str:
    """Get cashflow statement from Tushare Pro.

    Args:
        ticker: A-share ticker symbol
        freq: Report frequency (annual/quarterly)
        curr_date: Current date

    Returns:
        CSV string containing cashflow data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(ticker)

        df = pro.cashflow(
            ts_code=ts_code,
            type=freq == "annual" and "1" or "2",
        )

        if df.empty:
            return f"No Tushare cashflow data found for {ticker}"

        df = df.head(4)

        header = f"# Tushare cashflow for {ticker}\n"
        header += f"# Report type: {freq}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare Pro\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare cashflow for {ticker}: {str(e)}")


def get_income_statement(
    ticker: Annotated[str, "A-share ticker symbol"],
    freq: Annotated[str, "报告频率：annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期"] = None,
) -> str:
    """Get income statement from Tushare Pro.

    Args:
        ticker: A-share ticker symbol
        freq: Report frequency (annual/quarterly)
        curr_date: Current date

    Returns:
        CSV string containing income statement data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(ticker)

        df = pro.income(
            ts_code=ts_code,
            type=freq == "annual" and "1" or "2",
        )

        if df.empty:
            return f"No Tushare income statement data found for {ticker}"

        df = df.head(4)

        header = f"# Tushare income statement for {ticker}\n"
        header += f"# Report type: {freq}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare Pro\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare income statement for {ticker}: {str(e)}")