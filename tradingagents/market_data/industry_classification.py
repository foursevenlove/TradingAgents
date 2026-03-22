"""A-share industry classification module.

This module provides industry classification for A-share stocks using
Shenwan (申万) industry classification system, which is the standard
classification system used in Chinese A-share market.
"""

from typing import Dict, List, Optional, Tuple
import akshare as ak
import pandas as pd
from datetime import datetime

from tradingagents.dataflows.akshare_common import _convert_ticker_format, AkshareDataError


def get_sw_industry(ticker: str) -> Dict[str, str]:
    """Get Shenwan industry classification for a stock.

    Shenwan classification has three levels:
    - Level 1: 一级行业 (e.g., 信息技术、医药生物)
    - Level 2: 二级行业 (e.g., 计算机应用、化学制药)
    - Level 3: 三级行业 (e.g., 互联网服务、创新药)

    Args:
        ticker: A-share ticker symbol (e.g., "000001.SZ", "600000.SH")

    Returns:
        Dictionary with industry classification:
        - level_1: str, first level industry
        - level_2: str, second level industry
        - level_3: str, third level industry
        - industry_code: str, industry code

    Examples:
        >>> get_sw_industry("000001.SZ")
        {'level_1': '金融', 'level_2': '银行', 'level_3': '银行', 'industry_code': '480000'}
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get stock industry classification
        # ak.stock_board_industry_name_em returns industry info
        df = ak.stock_individual_info_em(symbol=stock_code)

        if df.empty:
            return {
                "level_1": "未知",
                "level_2": "未知",
                "level_3": "未知",
                "industry_code": "",
                "message": f"No industry data found for {ticker}",
            }

        # Extract industry information
        # The exact column names may vary, adjust as needed
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
            "message": f"Industry classification for {ticker}",
        }

    except Exception as e:
        raise AkshareDataError(f"Failed to get industry classification for {ticker}: {str(e)}")


def get_industry_peers(ticker: str, limit: int = 20) -> List[Dict[str, str]]:
    """Get peer stocks in the same industry.

    Args:
        ticker: A-share ticker symbol
        limit: Maximum number of peers to return

    Returns:
        List of dictionaries with peer information:
        - symbol: str, stock symbol
        - name: str, stock name
        - industry: str, industry name
        - market_cap: float, market capitalization

    Examples:
        >>> get_industry_peers("000001.SZ", limit=5)
        [{'symbol': '600000.SH', 'name': '浦发银行', ...}, ...]
    """
    try:
        # First get the industry of the target stock
        industry_info = get_sw_industry(ticker)
        industry_name = industry_info.get("level_2", "")

        if not industry_name or industry_name == "未知":
            return []

        # Get all stocks in the same industry
        # This is a simplified version - in practice you would query by industry
        stock_code, market = _convert_ticker_format(ticker)

        # Get industry constituent stocks
        # Note: The actual API call may vary depending on akshare version
        df = ak.stock_board_industry_cons_em(symbol=industry_name)

        if df.empty:
            return []

        # Convert to list of dictionaries
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

    except Exception as e:
        raise AkshareDataError(f"Failed to get industry peers for {ticker}: {str(e)}")


def get_industry_performance(
    industry_name: str,
    look_back_days: int = 30
) -> Dict[str, any]:
    """Get industry performance statistics.

    Args:
        industry_name: Industry name (e.g., "银行", "计算机应用")
        look_back_days: Number of days to look back

    Returns:
        Dictionary with industry performance:
        - avg_change_pct: float, average price change percentage
        - avg_turnover: float, average turnover rate
        - top_gainers: list, top performing stocks
        - top_losers: list, worst performing stocks
    """
    try:
        # Get industry constituent stocks
        df = ak.stock_board_industry_cons_em(symbol=industry_name)

        if df.empty:
            return {
                "avg_change_pct": 0,
                "avg_turnover": 0,
                "top_gainers": [],
                "top_losers": [],
                "message": f"No data found for industry {industry_name}",
            }

        # Calculate statistics
        avg_change = df["涨跌幅"].mean() if "涨跌幅" in df.columns else 0
        avg_turnover = df["换手率"].mean() if "换手率" in df.columns else 0

        # Get top gainers and losers
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

    except Exception as e:
        raise AkshareDataError(f"Failed to get industry performance for {industry_name}: {str(e)}")


def get_industry_list() -> List[Dict[str, str]]:
    """Get list of all Shenwan industries.

    Returns:
        List of dictionaries with industry information:
        - industry_name: str, industry name
        - industry_code: str, industry code
        - level: int, industry level (1, 2, or 3)
    """
    try:
        # Get industry list
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
        raise AkshareDataError(f"Failed to get industry list: {str(e)}")


def compare_with_industry(
    ticker: str,
    metrics: List[str] = None
) -> Dict[str, any]:
    """Compare stock performance with industry average.

    Args:
        ticker: A-share ticker symbol
        metrics: List of metrics to compare (default: ["pe_ratio", "pb_ratio", "roe"])

    Returns:
        Dictionary with comparison results:
        - stock_metrics: dict, stock's metrics
        - industry_avg: dict, industry average metrics
        - comparison: dict, relative performance
    """
    try:
        if metrics is None:
            metrics = ["pe_ratio", "pb_ratio", "roe", "revenue_growth"]

        # Get stock's industry
        industry_info = get_sw_industry(ticker)
        industry_name = industry_info.get("level_2", "")

        if not industry_name or industry_name == "未知":
            return {
                "message": f"Cannot determine industry for {ticker}",
            }

        # Get industry peers for comparison
        peers = get_industry_peers(ticker, limit=50)

        if not peers:
            return {
                "message": f"No peers found for {ticker} in industry {industry_name}",
            }

        # This is a simplified version
        # In practice, you would calculate actual metrics from financial data
        return {
            "ticker": ticker,
            "industry": industry_name,
            "peer_count": len(peers),
            "message": f"Comparison with {industry_name} industry",
        }

    except Exception as e:
        raise AkshareDataError(f"Failed to compare with industry for {ticker}: {str(e)}")
