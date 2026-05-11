"""Tushare Pro stock screening data for recommendation system.

Provides market-wide screening data using Tushare Pro API:
- Daily basic indicators (PE, PB, turnover, market cap)
- Money flow (main force inflow/outflow)
- Limit-up list (涨停清单)
- Top list (龙虎榜)

Requires TUSHARE_TOKEN environment variable.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

from .tushare_stock import TushareDataError


def _get_pro_api():
    """Get Tushare Pro API instance."""
    if not TUSHARE_AVAILABLE:
        raise TushareDataError("tushare package not installed")

    # Try to load from .env if not in environment
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            token = os.environ.get("TUSHARE_TOKEN")
        except ImportError:
            pass

    if not token:
        raise TushareDataError("TUSHARE_TOKEN not set")
    return ts.pro_api(token)


def _get_trade_date(date_str: str = None) -> str:
    """Get trade date in YYYYMMDD format.
    If date is weekend/holiday, returns the most recent trade date.
    """
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        dt = datetime.now()

    # Simple adjustment: if weekend, go back to Friday
    weekday = dt.weekday()
    if weekday >= 5:  # Saturday or Sunday
        days_back = weekday - 4  # Sat=2, Sun=3 -> back to Friday
        dt = dt - timedelta(days=days_back)

    return dt.strftime("%Y%m%d")


def get_daily_basic(trade_date: str = None) -> pd.DataFrame:
    """Get daily basic indicators for all stocks.

    Uses tushare pro.daily_basic().
    Returns: ts_code, name, close, pe, pb, turnover_rate, total_mv, circ_mv, etc.

    Args:
        trade_date: Date in YYYYMMDD or YYYY-MM-DD format. Defaults to latest trade date.
    """
    pro = _get_pro_api()
    td = _get_trade_date(trade_date)

    try:
        df = pro.daily_basic(trade_date=td)
        if df.empty:
            raise TushareDataError(f"No daily_basic data for {td}")
        return df
    except Exception as e:
        raise TushareDataError(f"Failed to get daily_basic: {e}")


def get_moneyflow(trade_date: str = None) -> pd.DataFrame:
    """Get individual stock money flow data.

    Uses tushare pro.moneyflow().
    Returns: ts_code, name, buy_sm_amount, sell_sm_amount, net_mf_amount, etc.

    Args:
        trade_date: Date in YYYYMMDD or YYYY-MM-DD format.
    """
    pro = _get_pro_api()
    td = _get_trade_date(trade_date)

    try:
        df = pro.moneyflow(trade_date=td)
        if df.empty:
            raise TushareDataError(f"No moneyflow data for {td}")
        return df
    except Exception as e:
        raise TushareDataError(f"Failed to get moneyflow: {e}")


def get_limit_list(trade_date: str = None) -> pd.DataFrame:
    """Get limit-up/limit-down list.

    Uses tushare pro.limit_list_d().
    Returns: ts_code, name, close, pct_chg, fc_ratio, fl_ratio, limit_type, etc.

    Args:
        trade_date: Date in YYYYMMDD or YYYY-MM-DD format.
    """
    pro = _get_pro_api()
    td = _get_trade_date(trade_date)

    try:
        df = pro.limit_list_d(trade_date=td)
        if df.empty:
            raise TushareDataError(f"No limit_list data for {td}")
        return df
    except Exception as e:
        raise TushareDataError(f"Failed to get limit_list: {e}")


def screen_stocks_tushare(
    trade_date: str = None,
    min_market_cap: float = 50,  # 50亿 (unit: 亿元 in tushare)
    max_pe: float = 100,
    min_turnover: float = 0.5,  # %
    exclude_st: bool = True,
    exclude_kcb: bool = True,
    top_n: int = 100,
) -> pd.DataFrame:
    """Screen stocks using Tushare Pro data.

    Combines daily_basic, moneyflow, and limit_list data to generate
    a ranked list of candidate stocks.

    Args:
        trade_date: Date (YYYY-MM-DD or YYYYMMDD). Defaults to latest trade date.
        min_market_cap: Minimum total market cap in 亿元 (default 50)
        max_pe: Maximum PE ratio
        min_turnover: Minimum turnover rate (%)
        exclude_st: Exclude ST stocks
        exclude_kcb: Exclude 科创板 (688XXX)
        top_n: Return top N stocks

    Returns:
        DataFrame with screened stocks and composite scores
    """
    pro = _get_pro_api()
    td = _get_trade_date(trade_date)

    # 1. Get daily basic indicators
    basic_df = get_daily_basic(trade_date)

    # Rename columns for consistency
    basic_df = basic_df.rename(columns={
        "ts_code": "code",
        "pe": "pe_ratio",
        "pb": "pb_ratio",
        "turnover_rate": "turnover",
        "total_mv": "market_cap",
        "circ_mv": "circ_cap",
    })

    # 2. Base filtering
    filtered = basic_df.copy()

    # Exclude ST (no name field in daily_basic, use ts_code pattern or skip)
    # daily_basic doesn't have name, we filter by code pattern

    # Exclude 科创板
    if exclude_kcb:
        filtered = filtered[~filtered["code"].str.startswith("688")]

    # Market cap filter (unit: 万元 in tushare daily_basic)
    # total_mv is in 万元 (10k yuan)
    min_mv_wan = min_market_cap * 10000  # Convert 亿元 to 万元
    filtered = filtered[filtered["market_cap"] >= min_mv_wan]

    # PE filter
    if "pe_ratio" in filtered.columns:
        filtered = filtered[
            (filtered["pe_ratio"] > 0) & (filtered["pe_ratio"] < max_pe)
        ]

    # Turnover filter
    if "turnover" in filtered.columns:
        filtered = filtered[filtered["turnover"] >= min_turnover]

    # 3. Add money flow data
    try:
        mf_df = get_moneyflow(trade_date)
        mf_cols = ["ts_code", "net_mf_amount", "buy_sm_amount", "sell_sm_amount"]
        mf_available = [c for c in mf_cols if c in mf_df.columns]
        if mf_available:
            mf_subset = mf_df[mf_available].copy()
            mf_subset = mf_subset.rename(columns={"ts_code": "code"})
            filtered = filtered.merge(mf_subset, on="code", how="left")
    except Exception:
        pass

    # 4. Add limit-up data
    try:
        zt_df = get_limit_list(trade_date)
        if not zt_df.empty and "ts_code" in zt_df.columns:
            # Only limit-up stocks (pct_chg >= 9.9)
            zt_up = zt_df[zt_df.get("limit_type", "").str.contains("U", na=False)]
            if not zt_up.empty:
                zt_subset = zt_up[["ts_code", "pct_chg", "fc_ratio", "fl_ratio"]].copy()
                zt_subset = zt_subset.rename(columns={"ts_code": "code"})
                zt_subset["is_limit_up"] = True
                filtered = filtered.merge(zt_subset, on="code", how="left")
                filtered["is_limit_up"] = filtered["is_limit_up"].fillna(False)
    except Exception:
        filtered["is_limit_up"] = False

    # 5. Calculate composite score
    filtered["score"] = 0.0

    # Get price change from daily data (need pro.daily for this)
    try:
        daily_df = pro.daily(trade_date=td)
        if not daily_df.empty and "ts_code" in daily_df.columns:
            daily_subset = daily_df[["ts_code", "pct_chg"]].copy()
            daily_subset = daily_subset.rename(columns={"ts_code": "code", "pct_chg": "change_pct"})
            filtered = filtered.merge(daily_subset, on="code", how="left")
    except Exception:
        filtered["change_pct"] = 0.0

    # Technical score (price change)
    if "change_pct" in filtered.columns:
        filtered["tech_score"] = filtered["change_pct"].fillna(0).clip(upper=10) / 10 * 30
        filtered["score"] += filtered["tech_score"]

    # Limit-up bonus
    if "is_limit_up" in filtered.columns:
        filtered["score"] += filtered["is_limit_up"].astype(float) * 15

    # Fund flow score
    if "net_mf_amount" in filtered.columns:
        flow = filtered["net_mf_amount"].fillna(0)
        # net_mf_amount is in 万元, normalize per 1000万
        flow_score = (flow / 1000).clip(lower=-10, upper=20) * 1.5
        filtered["fund_score"] = flow_score
        filtered["score"] += flow_score

    # 6. Sort and return
    result = filtered.sort_values("score", ascending=False).head(top_n)

    # Select output columns
    output_cols = ["code", "close", "change_pct", "turnover", "pe_ratio", "market_cap"]
    if "net_mf_amount" in result.columns:
        output_cols.append("net_mf_amount")
    if "is_limit_up" in result.columns:
        output_cols.append("is_limit_up")
    output_cols.append("score")

    available_cols = [c for c in output_cols if c in result.columns]

    # Add stock name from stock_basic
    try:
        stock_basic = pro.stock_basic(exchange="", list_status="L",
                                       fields="ts_code,name")
        stock_basic = stock_basic.rename(columns={"ts_code": "code"})
        result = result.merge(stock_basic, on="code", how="left")
    except Exception:
        result["name"] = ""

    # Reorder: code, name, then rest
    final_cols = ["code", "name"] + [c for c in available_cols if c not in ["code", "name"]]
    return result[final_cols].reset_index(drop=True)
