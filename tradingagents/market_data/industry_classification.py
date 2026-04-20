"""A-share industry classification module.

This module provides industry classification for A-share stocks using
cninfo (巨潮资讯) as the primary source, with eastmoney as fallback
when network access is available.
"""

from typing import Dict, List, Optional, Tuple
import akshare as ak
import pandas as pd
from datetime import datetime

from tradingagents.dataflows.akshare_common import _convert_ticker_format, AkshareDataError


def get_sw_industry(ticker: str) -> Dict[str, str]:
    """Get industry classification for a stock.

    Uses cninfo (巨潮资讯) as primary source (stable, no eastmoney dependency).
    Falls back to eastmoney if cninfo is unavailable.

    Args:
        ticker: A-share ticker symbol (e.g., "000001.SZ", "600000.SH")

    Returns:
        Dictionary with industry classification info
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Primary: cninfo (巨潮资讯) - stable and doesn't require eastmoney network
        try:
            df = ak.stock_profile_cninfo(symbol=stock_code)
            if not df.empty:
                industry_info = {}
                for col in df.columns:
                    val = df[col].iloc[0] if not df.empty else ""
                    if "行业" in str(col) or "industry" in str(col).lower():
                        industry_info[col] = val

                # Extract industry from profile
                main_industry = industry_info.get("所属行业", "未知")

                return {
                    "level_1": main_industry,
                    "level_2": industry_info.get("细分行业", main_industry),
                    "level_3": industry_info.get("行业分类", main_industry),
                    "industry_code": "",
                    "ticker": ticker,
                    "company_name": df["公司名称"].iloc[0] if "公司名称" in df.columns else "",
                    "message": f"Industry classification for {ticker} from cninfo",
                }
        except Exception:
            pass  # cninfo may fail for some stocks

        # Fallback: eastmoney individual info (may fail due to network)
        try:
            df = ak.stock_individual_info_em(symbol=stock_code)
            if not df.empty:
                industry_info = {}
                for _, row in df.iterrows():
                    item = row.get("item", "")
                    value = row.get("value", "")
                    if "行业" in item:
                        industry_info[item] = value

                return {
                    "level_1": industry_info.get("所属行业", "未知"),
                    "level_2": industry_info.get("细分行业", "未知"),
                    "level_3": industry_info.get("行业分类", "未知"),
                    "industry_code": "",
                    "ticker": ticker,
                    "message": f"Industry classification for {ticker} from eastmoney",
                }
        except Exception:
            pass  # eastmoney may fail due to network issues

        return {
            "level_1": "未知",
            "level_2": "未知",
            "level_3": "未知",
            "industry_code": "",
            "ticker": ticker,
            "message": f"Could not determine industry for {ticker}",
        }

    except Exception as e:
        raise AkshareDataError(f"Failed to get industry classification for {ticker}: {str(e)}")


def get_industry_peers(ticker: str, limit: int = 20) -> List[Dict[str, str]]:
    """Get peer stocks in the same industry.

    Uses eastmoney board industry data when network is available.
    Falls back to basic info when eastmoney is unreachable.

    Args:
        ticker: A-share ticker symbol
        limit: Maximum number of peers to return

    Returns:
        List of dictionaries with peer information
    """
    try:
        # First get the industry of the target stock
        industry_info = get_sw_industry(ticker)
        industry_name = industry_info.get("level_1", "")

        if not industry_name or industry_name == "未知":
            return []

        stock_code, market = _convert_ticker_format(ticker)

        # Try eastmoney industry constituent stocks (may fail due to network)
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry_name)
            if not df.empty:
                peers = []
                for _, row in df.head(limit).iterrows():
                    peer = {
                        "symbol": row.get("代码", ""),
                        "name": row.get("名称", ""),
                        "industry": industry_name,
                        "market_cap": row.get("总市值", 0),
                        "pe_ratio": row.get("市盈率", 0),
                    }
                    peers.append(peer)
                return peers
        except Exception:
            pass  # eastmoney may be unreachable

        # Fallback: return minimal info based on industry name
        return [{
            "symbol": stock_code,
            "name": industry_info.get("company_name", ""),
            "industry": industry_name,
            "message": f"Industry: {industry_name}. Full peer list requires eastmoney network access.",
        }]

    except Exception as e:
        raise AkshareDataError(f"Failed to get industry peers for {ticker}: {str(e)}")


def get_industry_performance(
    industry_name: str,
    look_back_days: int = 30
) -> Dict[str, any]:
    """Get industry performance statistics.

    Uses eastmoney when network is available.
    Falls back to basic info when eastmoney is unreachable.

    Args:
        industry_name: Industry name (e.g., "银行", "计算机应用")
        look_back_days: Number of days to look back

    Returns:
        Dictionary with industry performance data
    """
    try:
        # Try eastmoney industry data (may fail due to network)
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry_name)

            if not df.empty:
                avg_change = df["涨跌幅"].mean() if "涨跌幅" in df.columns else 0
                avg_turnover = df["换手率"].mean() if "换手率" in df.columns else 0

                top_gainers = []
                top_losers = []

                if "涨跌幅" in df.columns:
                    df_sorted = df.sort_values("涨跌幅", ascending=False)
                    top_gainers = df_sorted.head(5)[["代码", "名称", "涨跌幅"]].to_dict("records")
                    top_losers = df_sorted.tail(5)[["代码", "名称", "涨跌幅"]].to_dict("records")

                return {
                    "industry_name": industry_name,
                    "avg_change_pct": round(avg_change, 2),
                    "avg_turnover": round(avg_turnover, 2),
                    "stock_count": len(df),
                    "top_gainers": top_gainers,
                    "top_losers": top_losers,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
        except Exception:
            pass  # eastmoney unreachable

        # Fallback: return minimal info
        return {
            "industry_name": industry_name,
            "avg_change_pct": 0,
            "avg_turnover": 0,
            "stock_count": 0,
            "top_gainers": [],
            "top_losers": [],
            "message": f"Industry '{industry_name}' performance data requires eastmoney network access",
        }

    except Exception as e:
        raise AkshareDataError(f"Failed to get industry performance for {industry_name}: {str(e)}")


def get_industry_list() -> List[Dict[str, str]]:
    """Get list of all Shenwan industries.

    Returns:
        List of dictionaries with industry information.
        May return empty list if eastmoney network is unavailable.
    """
    try:
        df = ak.stock_board_industry_name_em()
        if df.empty:
            return []

        industries = []
        for _, row in df.iterrows():
            industry = {
                "industry_name": row.get("板块名称", ""),
                "industry_code": row.get("板块代码", ""),
                "stock_count": row.get("公司数量", 0),
                "avg_change_pct": row.get("平均涨跌幅", 0),
            }
            industries.append(industry)

        return industries

    except Exception as e:
        # eastmoney may be unreachable
        return []


def compare_with_industry(
    ticker: str,
    metrics: List[str] = None
) -> Dict[str, any]:
    """Compare stock performance with industry average.

    Args:
        ticker: A-share ticker symbol
        metrics: List of metrics to compare (default: ["pe_ratio", "pb_ratio", "roe"])

    Returns:
        Dictionary with comparison results
    """
    try:
        if metrics is None:
            metrics = ["pe_ratio", "pb_ratio", "roe", "revenue_growth"]

        industry_info = get_sw_industry(ticker)
        industry_name = industry_info.get("level_1", "")

        if not industry_name or industry_name == "未知":
            return {
                "message": f"Cannot determine industry for {ticker}",
            }

        peers = get_industry_peers(ticker, limit=50)

        if not peers:
            return {
                "message": f"No peers found for {ticker} in industry {industry_name}",
            }

        return {
            "ticker": ticker,
            "industry": industry_name,
            "peer_count": len(peers),
            "message": f"Comparison with {industry_name} industry",
        }

    except Exception as e:
        raise AkshareDataError(f"Failed to compare with industry for {ticker}: {str(e)}")
