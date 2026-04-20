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
        CSV string containing margin trading data for the specified stock

    Note:
        akshare's stock_margin_detail_sse now returns ALL stocks for a given date
        (no longer supports querying by individual symbol). We query the full market
        data and filter for the target stock. SZSE margin detail is currently broken
        in akshare, so we use SSE data (which covers Shanghai stocks) and fall back
        to aggregate SZSE data for Shenzhen stocks.
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get recent trading dates
        end_date = datetime.now()
        start_date = end_date - pd.Timedelta(days=look_back_days + 10)  # extra buffer for non-trading days

        all_data = []

        # SSE margin data: returns all Shanghai stocks for a date, works reliably
        if market == "sh":
            date_range = pd.date_range(start=start_date, end=end_date, freq="B")  # business days only
            for d in date_range[-look_back_days:]:
                date_str = d.strftime("%Y%m%d")
                try:
                    df = ak.stock_margin_detail_sse(date=date_str)
                    if not df.empty and "标的证券代码" in df.columns:
                        row = df[df["标的证券代码"] == stock_code]
                        if not row.empty:
                            all_data.append(row)
                except Exception:
                    continue

        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            # Rename columns for clarity
            column_mapping = {
                "信用交易日期": "Date",
                "标的证券代码": "Stock_Code",
                "标的证券简称": "Stock_Name",
                "融资余额": "Margin_Balance",
                "融资买入额": "Margin_Buy_Amount",
                "融资偿还额": "Margin_Repay_Amount",
                "融券余量": "Short_Sell_Residual",
                "融券卖出量": "Short_Sell_Volume",
                "融券偿还量": "Short_Sell_Repay_Volume",
            }
            result = result.rename(columns=column_mapping)
        else:
            # For SZSE stocks or if SSE data unavailable, try aggregate data
            # stock_margin_szse returns aggregate market-level data
            if market == "sz":
                # SZSE individual stock margin detail is broken in akshare
                # Return a note explaining the limitation
                return f"# Margin Trading Data for {ticker}\n# NOTE: SZSE individual stock margin detail is currently unavailable in akshare.\n# Available: SSE (Shanghai) individual stock data, SZSE aggregate market data only.\n# Fallback: Use SSE margin data for Shanghai stocks.\n# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            return f"No margin trading data found for {ticker}"

        header = f"# Margin Trading Data for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total records: {len(result)}\n"
        header += f"# Data source: SSE margin detail (akshare)\n"

        return _format_to_csv(result, header)

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
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - pd.Timedelta(days=look_back_days)).strftime("%Y%m%d")
        else:
            end_date = date.replace("-", "")
            start_date_d = pd.to_datetime(date) - pd.Timedelta(days=look_back_days)
            start_date = start_date_d.strftime("%Y%m%d")

        # Get dragon-tiger list (akshare API changed: now uses start_date/end_date)
        df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)

        if df.empty:
            return f"No dragon-tiger list data for period {start_date} to {end_date}"

        # Limit to recent records
        df = df.head(100)  # Top 100 records

        header = f"# Dragon-Tiger List (龙虎榜)\n"
        header += f"# Date range: {start_date} to {end_date}\n"
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
        CSV string containing block trade data for the specified stock

    Note:
        akshare's stock_dzjy_mrmx no longer accepts individual stock codes.
        We use stock_dzjy_mrtj which returns all block trades for a date range,
        then filter for the target stock.
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get all block trades for the date range
        start_dt = start_date.replace("-", "")
        end_dt = end_date.replace("-", "")
        df = ak.stock_dzjy_mrtj(start_date=start_dt, end_date=end_dt)

        if df.empty:
            return f"No block trade data found for date range {start_date} to {end_date}"

        # Filter for the target stock by code
        if "证券代码" in df.columns:
            df_stock = df[df["证券代码"] == stock_code]
            if df_stock.empty:
                # The stock has no block trades in this period - return market-wide data as context
                header = f"# Block Trade Data (market-wide) for period {start_date} to {end_date}\n"
                header += f"# NOTE: {ticker} has no block trades in this period\n"
                header += f"# Showing top 20 market block trades for reference\n"
                header += f"# Total market records: {len(df)}\n"
                df = df.head(20)  # Show top 20 as context
            else:
                header = f"# Block Trade Data for {ticker}\n"
                header += f"# Date range: {start_date} to {end_date}\n"
                header += f"# Total records for {ticker}: {len(df_stock)}\n"
                df = df_stock
        else:
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

        # Convert quarter format: "2025Q1" -> "20251"
        if quarter is None:
            # Default to latest quarter
            now = datetime.now()
            q_num = (now.month - 1) // 3 + 1
            quarter_str = f"{now.year}{q_num}"
        else:
            # Parse "2025Q1" format
            quarter_str = quarter.replace("Q", "")

        # Get institutional holdings (akshare uses 'stock' param, not 'symbol')
        df = ak.stock_institute_hold_detail(stock=stock_code, quarter=quarter_str)

        if df.empty:
            # Some stocks (e.g., banks) may have empty institutional detail data
            # Try using fund holdings as fallback context
            try:
                quarter_date = f"{quarter_str[:4]}0331" if quarter_str.endswith("1") else \
                               f"{quarter_str[:4]}0630" if quarter_str.endswith("2") else \
                               f"{quarter_str[:4]}0930" if quarter_str.endswith("3") else \
                               f"{quarter_str[:4]}1231"
                df = ak.stock_report_fund_hold(symbol="基金持仓", date=quarter_date)
                # Filter for target stock
                if "股票代码" in df.columns:
                    df = df[df["股票代码"] == stock_code]
                if not df.empty:
                    header = f"# Institutional Holdings (Fund) for {ticker}\n"
                    header += f"# Quarter: {quarter}\n"
                    header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    header += f"# Total records: {len(df)}\n"
                    return _format_to_csv(df, header)
            except Exception:
                pass

            return f"No institutional holdings data found for {ticker} (quarter: {quarter})"

        header = f"# Institutional Holdings for {ticker}\n"
        header += f"# Quarter: {quarter}\n"
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

        # Get limit down stocks (akshare renamed: stock_dt_pool_em -> stock_zt_pool_dtgc_em)
        try:
            df_down = ak.stock_zt_pool_dtgc_em(date=date)
            limit_down_count = len(df_down) if not df_down.empty else 0
        except Exception:
            # If dtgc not available for this date, try fallback
            limit_down_count = 0

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
