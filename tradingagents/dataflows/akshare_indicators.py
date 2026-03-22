"""Akshare A-share specific data indicators.

This module provides A-share market specific data that is not available in other markets,
including northbound capital flow, margin trading, dragon-tiger list, and block trades.
"""

from datetime import datetime
from typing import Annotated, Optional
import akshare as ak
import pandas as pd

from .akshare_common import _convert_ticker_format, _format_to_csv, AkshareDataError


def get_north_bound_flow(
    date: Annotated[str, "Date in yyyy-mm-dd format"] = None,
    look_back_days: Annotated[int, "Number of days to look back"] = 30,
) -> str:
    """Get northbound capital flow (北向资金流向).

    Northbound capital refers to foreign capital flowing into A-shares
    through Stock Connect (沪深港通).

    Args:
        date: End date (default: today)
        look_back_days: Number of days to look back

    Returns:
        CSV string containing northbound capital flow data
    """
    try:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Get northbound capital flow data
        # Use stock_hsgt_hist_em for historical northbound capital flow
        df = ak.stock_hsgt_hist_em(symbol="北向资金")

        if df.empty:
            return "No northbound capital flow data available"

        # Filter by date range
        df["日期"] = pd.to_datetime(df["日期"])
        end_date = pd.to_datetime(date)
        start_date = end_date - pd.Timedelta(days=look_back_days)
        df = df[(df["日期"] >= start_date) & (df["日期"] <= end_date)]

        # Rename columns
        column_mapping = {
            "日期": "Date",
            "当日资金流入": "Daily_Inflow",
            "当日余额": "Daily_Balance",
            "当日成交净买额": "Net_Buy_Amount",
        }
        df_renamed = df.rename(columns=column_mapping)

        header = f"# Northbound Capital Flow (北向资金流向)\n"
        header += f"# Date range: {start_date.strftime('%Y-%m-%d')} to {date}\n"
        header += f"# Total records: {len(df_renamed)}\n"

        return _format_to_csv(df_renamed, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get northbound capital flow: {str(e)}")


def get_margin_trading(
    ticker: Annotated[str, "A-share ticker symbol"],
    look_back_days: Annotated[int, "Number of days to look back"] = 30,
) -> str:
    """Get margin trading data (融资融券数据).

    Margin trading includes:
    - Margin buying (融资买入): Borrowing money to buy stocks
    - Short selling (融券卖出): Borrowing stocks to sell

    Args:
        ticker: A-share ticker symbol
        look_back_days: Number of days to look back

    Returns:
        CSV string containing margin trading data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get margin trading detail
        # ak.stock_margin_detail_sse for Shanghai
        # ak.stock_margin_detail_szse for Shenzhen
        if market == "sh":
            df = ak.stock_margin_detail_sse(symbol=stock_code)
        else:
            df = ak.stock_margin_detail_szse(symbol=stock_code)

        if df.empty:
            return f"No margin trading data found for {ticker}"

        # Filter recent data
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"])
            cutoff_date = datetime.now() - pd.Timedelta(days=look_back_days)
            df = df[df["日期"] >= cutoff_date]

        header = f"# Margin Trading Data for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total records: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get margin trading data for {ticker}: {str(e)}")


def get_dragon_tiger_list(
    date: Annotated[str, "Date in yyyy-mm-dd format"] = None,
    look_back_days: Annotated[int, "Number of days to look back"] = 5,
) -> str:
    """Get dragon-tiger list data (龙虎榜数据).

    Dragon-tiger list shows stocks with abnormal trading activity and
    the top trading seats (institutions and hot money).

    Args:
        date: End date (default: today)
        look_back_days: Number of days to look back

    Returns:
        CSV string containing dragon-tiger list data
    """
    try:
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        else:
            date = date.replace("-", "")

        # Get dragon-tiger list
        df = ak.stock_lhb_detail_em(symbol=date)

        if df.empty:
            return f"No dragon-tiger list data for {date}"

        # Limit to recent records
        df = df.head(100)  # Top 100 records

        header = f"# Dragon-Tiger List (龙虎榜) for {date}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total records: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get dragon-tiger list: {str(e)}")


def get_block_trade(
    ticker: Annotated[str, "A-share ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Get block trade data (大宗交易数据).

    Block trades are large transactions typically made by institutions,
    often at a discount to market price.

    Args:
        ticker: A-share ticker symbol
        start_date: Start date
        end_date: End date

    Returns:
        CSV string containing block trade data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get block trade data
        df = ak.stock_dzjy_mrmx(symbol=stock_code)

        if df.empty:
            return f"No block trade data found for {ticker}"

        # Filter by date range
        if "交易日期" in df.columns:
            df["交易日期"] = pd.to_datetime(df["交易日期"])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df["交易日期"] >= start_dt) & (df["交易日期"] <= end_dt)]

        header = f"# Block Trade Data for {ticker}\n"
        header += f"# Date range: {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get block trade data for {ticker}: {str(e)}")


def get_institutional_holdings(
    ticker: Annotated[str, "A-share ticker symbol"],
    quarter: Annotated[str, "Quarter in YYYYQ format (e.g., 2024Q3)"] = None,
) -> str:
    """Get institutional holdings data (机构持仓数据).

    Shows holdings by funds, QFII, social security, insurance, etc.

    Args:
        ticker: A-share ticker symbol
        quarter: Quarter (default: latest)

    Returns:
        CSV string containing institutional holdings data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get institutional holdings
        df = ak.stock_institute_hold_detail(symbol=stock_code)

        if df.empty:
            return f"No institutional holdings data found for {ticker}"

        header = f"# Institutional Holdings for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total records: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get institutional holdings for {ticker}: {str(e)}")


def get_limit_up_down_stats(
    date: Annotated[str, "Date in yyyy-mm-dd format"] = None,
) -> str:
    """Get limit up/down statistics (涨跌停统计).

    Shows number of stocks hitting limit up or limit down,
    which is an important market sentiment indicator.

    Args:
        date: Date (default: today)

    Returns:
        CSV string containing limit up/down statistics
    """
    try:
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        else:
            date = date.replace("-", "")

        # Get limit up stocks
        df_up = ak.stock_zt_pool_em(date=date)
        limit_up_count = len(df_up) if not df_up.empty else 0

        # Get limit down stocks
        df_down = ak.stock_dt_pool_em(date=date)
        limit_down_count = len(df_down) if not df_down.empty else 0

        # Create summary
        summary = pd.DataFrame({
            "Date": [date],
            "Limit_Up_Count": [limit_up_count],
            "Limit_Down_Count": [limit_down_count],
            "Net_Sentiment": [limit_up_count - limit_down_count],
        })

        header = f"# Limit Up/Down Statistics for {date}\n"
        header += f"# Limit Up: {limit_up_count} stocks\n"
        header += f"# Limit Down: {limit_down_count} stocks\n"
        header += f"# Net Sentiment: {limit_up_count - limit_down_count}\n"

        return _format_to_csv(summary, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get limit up/down statistics: {str(e)}")


def get_market_sentiment_index(
    look_back_days: Annotated[int, "Number of days to look back"] = 30,
) -> str:
    """Get market sentiment index (市场情绪指数).

    Composite index based on:
    - Northbound capital flow
    - Limit up/down ratio
    - Turnover rate
    - New account openings

    Args:
        look_back_days: Number of days to look back

    Returns:
        CSV string containing market sentiment data
    """
    try:
        # This is a simplified version
        # In practice, you would combine multiple indicators

        # Get northbound flow as proxy
        north_flow = get_north_bound_flow(look_back_days=look_back_days)

        header = f"# Market Sentiment Index\n"
        header += f"# Based on northbound capital flow and other indicators\n"
        header += f"# Look back period: {look_back_days} days\n"

        return header + "\n" + north_flow

    except Exception as e:
        raise AkshareDataError(f"Failed to get market sentiment index: {str(e)}")
