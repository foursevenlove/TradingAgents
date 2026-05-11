"""Akshare stock screening data for recommendation system.

Provides market-wide screening data using akshare (Sina as primary source).

Available interfaces:
- stock_zh_a_spot: Sina real-time quotes (works without eastmoney network)
- stock_zh_a_daily: Historical daily data for individual stocks

Note: Eastmoney interfaces may be blocked in some network environments,
so we use Sina as the primary data source.
"""

from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

from .akshare_common import AkshareDataError


def get_a_share_spot_sina() -> pd.DataFrame:
    """Get real-time A-share market data from Sina.

    Uses akshare.stock_zh_a_spot() (Sina source, more stable).
    Returns DataFrame with: 代码, 名称, 最新价, 涨跌额, 涨跌幅, 成交量, 成交额, etc.

    Note: Does not include PE, market cap, turnover rate.
    """
    if not AKSHARE_AVAILABLE:
        raise AkshareDataError("akshare not installed")

    try:
        df = ak.stock_zh_a_spot()
        return df
    except Exception as e:
        raise AkshareDataError(f"Failed to get A-share spot from Sina: {e}")


def get_stock_daily_sina(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """Get daily historical data for a single stock from Sina.

    Uses akshare.stock_zh_a_daily().
    Returns DataFrame with: date, open, high, low, close, volume, amount, turnover.

    Args:
        symbol: Stock code without market suffix (e.g., "600000" for SH, "000001" for SZ)
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)
    """
    if not AKSHARE_AVAILABLE:
        raise AkshareDataError("akshare not installed")

    try:
        # Convert symbol format: 600000.SH -> sh600000, 000001.SZ -> sz000001
        if "." in symbol:
            code, market = symbol.split(".")
            if market.upper() == "SH":
                symbol = f"sh{code}"
            elif market.upper() == "SZ":
                symbol = f"sz{code}"
            elif market.upper() == "BJ":
                symbol = f"bj{code}"
            else:
                symbol = code

        df = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date, end_date=end_date)
        return df
    except Exception as e:
        raise AkshareDataError(f"Failed to get daily data for {symbol}: {e}")


def screen_stocks(
    min_change_pct: float = -5,  # Minimum change (exclude big drops)
    max_change_pct: float = 15,  # Maximum change (avoid excessive volatility)
    min_amount: float = 1e8,     # Minimum trading amount (1亿, ensure liquidity)
    exclude_st: bool = True,
    exclude_kcb: bool = True,    # 科创板
    exclude_bj: bool = True,     # 北交所
    top_n: int = 100,
) -> pd.DataFrame:
    """Screen stocks based on price change and trading amount.

    Uses Sina real-time data which is more stable than Eastmoney.

    Scoring factors:
    - Price change (涨跌幅): Higher positive change = higher score
    - Trading amount (成交额): Higher volume = more attention
    - Price momentum (涨跌额): Absolute price movement

    Args:
        min_change_pct: Minimum price change percentage
        max_change_pct: Maximum price change percentage
        min_amount: Minimum trading amount in RMB
        exclude_st: Whether to exclude ST stocks
        exclude_kcb: Whether to exclude 科创板 (688XXX)
        exclude_bj: Whether to exclude 北交所 (bj prefix)
        top_n: Return top N stocks

    Returns:
        DataFrame with screened stocks and scores
    """
    if not AKSHARE_AVAILABLE:
        raise AkshareDataError("akshare not installed")

    # 1. Get real-time data from Sina
    spot_df = get_a_share_spot_sina()

    # Standardize column names
    col_map = {
        "代码": "code",
        "名称": "name",
        "最新价": "price",
        "涨跌额": "change",
        "涨跌幅": "change_pct",
        "成交量": "volume",
        "成交额": "amount",
    }
    for cn, en in col_map.items():
        if cn in spot_df.columns:
            spot_df[en] = spot_df[cn]

    # Ensure required columns
    required = ["code", "name", "change_pct", "amount", "price"]
    for col in required:
        if col not in spot_df.columns:
            raise AkshareDataError(f"Required column '{col}' not found. Available: {spot_df.columns.tolist()}")

    # 2. Base filtering
    filtered = spot_df.copy()

    # Exclude ST
    if exclude_st and "name" in filtered.columns:
        filtered = filtered[~filtered["name"].astype(str).str.contains("ST|退|N", na=False)]

    # Exclude 北交所 (bj prefix)
    if exclude_bj and "code" in filtered.columns:
        filtered = filtered[~filtered["code"].astype(str).str.startswith("bj")]

    # Exclude 科创板 (688XXX) - these are in SH market
    if exclude_kcb and "code" in filtered.columns:
        # 科创板 codes are 688xxx but in sina they may have sh prefix
        filtered = filtered[~filtered["code"].astype(str).str.contains("688|689")]

    # Price change filter
    if "change_pct" in filtered.columns:
        filtered["change_pct_num"] = pd.to_numeric(filtered["change_pct"], errors="coerce")
        filtered = filtered[
            (filtered["change_pct_num"] >= min_change_pct) &
            (filtered["change_pct_num"] <= max_change_pct)
        ]

    # Trading amount filter (ensure liquidity)
    if "amount" in filtered.columns:
        filtered["amount_num"] = pd.to_numeric(filtered["amount"], errors="coerce")
        filtered = filtered[filtered["amount_num"] >= min_amount]

    # 3. Calculate composite score
    filtered["score"] = 0.0

    # Technical score: price change (higher = better for upward momentum)
    if "change_pct_num" in filtered.columns:
        # Score: 0-50 points for price change
        # Positive change scores higher, cap at 10% for safety
        filtered["tech_score"] = filtered["change_pct_num"].clip(lower=0, upper=10) / 10 * 50
        filtered["score"] += filtered["tech_score"].fillna(0)

    # Volume score: trading amount (higher = more attention)
    if "amount_num" in filtered.columns:
        # Score: 0-30 points for volume
        # Normalize by log scale to handle wide range
        import numpy as np
        filtered["vol_score"] = np.log10(filtered["amount_num"].clip(lower=1e8)) * 3
        filtered["vol_score"] = filtered["vol_score"].clip(upper=30)
        filtered["score"] += filtered["vol_score"].fillna(0)

    # Price momentum: absolute price change
    if "change" in filtered.columns:
        filtered["change_num"] = pd.to_numeric(filtered["change"], errors="coerce")
        filtered["momentum_score"] = filtered["change_num"].abs().clip(upper=2) / 2 * 20
        filtered["score"] += filtered["momentum_score"].fillna(0)

    # 4. Sort and return
    result = filtered.sort_values("score", ascending=False).head(top_n)

    # Select output columns
    output_cols = ["code", "name", "price", "change", "change_pct", "amount", "score"]
    available_cols = [c for c in output_cols if c in result.columns]

    return result[available_cols].reset_index(drop=True)


def get_top_gainers(top_n: int = 20) -> pd.DataFrame:
    """Get top gaining stocks today.

    Args:
        top_n: Number of stocks to return

    Returns:
        DataFrame with top gainers
    """
    df = screen_stocks(
        min_change_pct=3,  # Only positive gains
        max_change_pct=15,
        min_amount=5e8,    # At least 5亿 turnover
        top_n=top_n,
    )
    return df


def get_high_activity_stocks(top_n: int = 30) -> pd.DataFrame:
    """Get stocks with high trading activity.

    Args:
        top_n: Number of stocks to return

    Returns:
        DataFrame with high activity stocks (sorted by amount)
    """
    df = screen_stocks(
        min_change_pct=-5,
        max_change_pct=15,
        min_amount=1e9,    # At least 10亿 turnover
        top_n=top_n,
    )
    return df.sort_values("amount", ascending=False).head(top_n)


def filter_by_industry_keywords(
    stocks_df: pd.DataFrame,
    keywords: List[str],
    industry_col: str = None,
) -> pd.DataFrame:
    """Filter stocks by industry keywords.

    Since Sina data doesn't have industry field, this function
    is a placeholder that requires additional industry data.

    Args:
        stocks_df: DataFrame from screen_stocks
        keywords: List of industry keywords to match
        industry_col: Column name for industry (if available)

    Returns:
        Filtered DataFrame (returns original if no industry data)
    """
    # Sina data doesn't have industry classification
    # This is a placeholder - actual implementation needs industry data source
    if industry_col and industry_col in stocks_df.columns:
        pattern = "|".join(keywords)
        return stocks_df[stocks_df[industry_col].str.contains(pattern, case=False, na=False)]
    else:
        # Return original - need to use get_sw_industry for each stock later
        return stocks_df