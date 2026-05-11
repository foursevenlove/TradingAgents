"""Akshare data source for A-share market.

This module provides data access for Chinese A-share stocks using akshare library.
It serves as the main entry point for all akshare-related data functions.
"""

# Import stock data functions
from .akshare_stock import get_stock

# Import indicator functions
from .akshare_indicator import get_indicator

# Import fundamental data functions
from .akshare_fundamentals import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)

# Import news data functions
from .akshare_news import (
    get_news,
    get_global_news,
    get_insider_transactions,
    get_company_news,
    get_industry_news,
    get_policy_news,
    get_recommendation_news,
)

# Import A-share specific indicators
from .akshare_indicators import (
    get_north_bound_flow,
    get_margin_trading,
    get_dragon_tiger_list,
    get_block_trade,
    get_institutional_holdings,
    get_limit_up_down_stats,
    get_market_sentiment_index,
    get_pledge_ratio,
)

# Import stock screening data
from .akshare_screening import (
    get_a_share_spot_sina as get_a_share_spot,
    screen_stocks,
    get_top_gainers,
    get_stock_daily_sina,
)

# Import common utilities and exceptions
from .akshare_common import AkshareDataError

__all__ = [
    # Stock data
    "get_stock",
    # Technical indicators
    "get_indicator",
    # Fundamental data
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    # News data
    "get_news",
    "get_global_news",
    "get_insider_transactions",
    "get_company_news",
    "get_industry_news",
    "get_policy_news",
    # A-share specific indicators
    "get_north_bound_flow",
    "get_margin_trading",
    "get_dragon_tiger_list",
    "get_block_trade",
    "get_institutional_holdings",
    "get_limit_up_down_stats",
    "get_market_sentiment_index",
    "get_pledge_ratio",
    # Stock screening
    "get_a_share_spot",
    "screen_stocks",
    "get_top_gainers",
    "get_stock_daily_sina",
    # Exceptions
    "AkshareDataError",
]
