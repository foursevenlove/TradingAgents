"""Stock Screener - Screen candidate stocks from market data.

Uses akshare Sina data source for real-time screening.
"""

import logging
import pandas as pd
from typing import List, Dict, Optional

from tradingagents.dataflows.akshare_screening import (
    screen_stocks,
    get_top_gainers,
    get_a_share_spot_sina,
)
from tradingagents.market_data.industry_classification import get_sw_industry


logger = logging.getLogger("tradingagents.web.recommendation.stock_screener")


class StockScreener:
    """Screen stocks based on technical and volume factors."""

    def __init__(self):
        pass

    def screen(
        self,
        min_change_pct: float = -5,
        max_change_pct: float = 15,
        min_amount: float = 1e8,
        exclude_st: bool = True,
        exclude_kcb: bool = True,
        exclude_bj: bool = True,
        top_n: int = 100,
    ) -> pd.DataFrame:
        """Screen stocks based on price change and volume.

        Args:
            min_change_pct: Minimum price change %
            max_change_pct: Maximum price change %
            min_amount: Minimum trading amount (RMB)
            exclude_st: Exclude ST stocks
            exclude_kcb: Exclude 科创板
            exclude_bj: Exclude 北交所
            top_n: Return top N stocks

        Returns:
            DataFrame with screened stocks and scores
        """
        return screen_stocks(
            min_change_pct=min_change_pct,
            max_change_pct=max_change_pct,
            min_amount=min_amount,
            exclude_st=exclude_st,
            exclude_kcb=exclude_kcb,
            exclude_bj=exclude_bj,
            top_n=top_n,
        )

    def get_top_gainers(self, top_n: int = 20) -> pd.DataFrame:
        """Get top gaining stocks.

        Args:
            top_n: Number of stocks

        Returns:
            DataFrame with top gainers
        """
        return get_top_gainers(top_n)

    def get_stock_with_industry(
        self,
        stock_code: str,
    ) -> Dict:
        """Get stock info with industry classification.

        Args:
            stock_code: Stock code (e.g., "sh600000" or "sz002281")

        Returns:
            Dict with stock info and industry
        """
        # Convert Sina format to standard format
        # sh600000 -> 600000.SH, sz002281 -> 002281.SZ
        if stock_code.startswith("sh"):
            code = stock_code[2:]
            ts_code = f"{code}.SH"
        elif stock_code.startswith("sz"):
            code = stock_code[2:]
            ts_code = f"{code}.SZ"
        elif stock_code.startswith("bj"):
            code = stock_code[2:]
            ts_code = f"{code}.BJ"
        else:
            # Assume it's already in correct format
            ts_code = stock_code

        # Get industry classification
        try:
            industry_info = get_sw_industry(ts_code)
            return {
                "code": stock_code,
                "ts_code": ts_code,
                "industry": industry_info.get("level_1", "未知"),
                "industry_detail": industry_info.get("level_2", "未知"),
            }
        except Exception as exc:
            logger.warning(
                "Failed to get industry classification for screened stock",
                exc_info=(type(exc), exc, exc.__traceback__),
                extra={"extra_data": {
                    "stage": "stock_screener_industry_lookup",
                    "stock_code": stock_code,
                    "ts_code": ts_code,
                }},
            )
            return {
                "code": stock_code,
                "ts_code": ts_code,
                "industry": "未知",
                "industry_detail": "未知",
            }

    def add_industry_to_stocks(
        self,
        stocks_df: pd.DataFrame,
        max_stocks: int = 50,
    ) -> pd.DataFrame:
        """Add industry classification to stocks DataFrame.

        Args:
            stocks_df: DataFrame from screen()
            max_stocks: Maximum stocks to process (API call limit)

        Returns:
            DataFrame with added 'industry' column
        """
        result = stocks_df.copy()
        result["industry"] = "未知"

        # Process top stocks only (avoid too many API calls)
        for i, row in result.head(max_stocks).iterrows():
            code = row.get("code", "")
            if code:
                info = self.get_stock_with_industry(code)
                result.at[i, "industry"] = info.get("industry", "未知")

        return result

    def filter_by_industry(
        self,
        stocks_df: pd.DataFrame,
        industry_keywords: List[str],
    ) -> pd.DataFrame:
        """Filter stocks by industry keywords.

        Args:
            stocks_df: DataFrame with 'industry' column
            industry_keywords: Keywords to match

        Returns:
            Filtered DataFrame
        """
        if "industry" not in stocks_df.columns:
            return stocks_df

        pattern = "|".join(industry_keywords)
        return stocks_df[
            stocks_df["industry"].str.contains(pattern, case=False, na=False)
        ]
