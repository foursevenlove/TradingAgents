"""Stock Recommendation Module for TradingAgents.

This module provides stock recommendation capabilities:
- NewsCacheManager: Local 30-day news cache with background updates
- NewsPreprocessor: LLM-based three-layer news processing
- ThemeExtractor: Extract investment themes from cached news
- ThemeTracker: Track themes across days using keyword combination
- StockScreener: Screen candidate stocks from market data
- IndustryMapper: Map themes to industries and stocks
- DailyRecommender: Generate daily recommendations (light analysis)
- WeeklyRecommender: Generate weekly recommendations (full analysis)
"""

from .news_cache_manager import NewsCacheManager, get_cache_manager
from .news_preprocessor import NewsPreprocessor, BatchPreprocessor
from .theme_extractor import ThemeExtractor
from .theme_tracker import ThemeTracker
from .stock_screener import StockScreener
from .industry_mapper import IndustryMapper
from .daily_recommender import DailyRecommender
from .weekly_recommender import WeeklyRecommender

__all__ = [
    "NewsCacheManager",
    "get_cache_manager",
    "NewsPreprocessor",
    "BatchPreprocessor",
    "ThemeExtractor",
    "ThemeTracker",
    "StockScreener",
    "IndustryMapper",
    "DailyRecommender",
    "WeeklyRecommender",
]