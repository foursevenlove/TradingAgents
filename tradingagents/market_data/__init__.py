"""A-share market data module.

This module provides market data specific to Chinese A-share market,
including industry classification, sector analysis, and market statistics.
"""

from .industry_classification import (
    get_sw_industry,
    get_industry_peers,
    get_industry_performance,
    get_industry_list,
    compare_with_industry,
)

__all__ = [
    "get_sw_industry",
    "get_industry_peers",
    "get_industry_performance",
    "get_industry_list",
    "compare_with_industry",
]
