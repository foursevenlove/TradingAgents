from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Annotated

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from .tushare_news import TushareDataError as TushareNewsDataError
from .tushare_stock import TushareDataError as TushareStockDataError
from .akshare import (
    get_stock as get_akshare_stock,
    get_indicator as get_akshare_indicator,
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
    get_news as get_akshare_news,
    get_global_news as get_akshare_global_news,
    get_insider_transactions as get_akshare_insider_transactions,
    get_company_news as get_akshare_company_news,
    get_industry_news as get_akshare_industry_news,
    get_policy_news as get_akshare_policy_news,
    # A-share specific indicators
    get_north_bound_flow as get_akshare_north_bound_flow,
    get_margin_trading as get_akshare_margin_trading,
    get_dragon_tiger_list as get_akshare_dragon_tiger_list,
    get_block_trade as get_akshare_block_trade,
    get_institutional_holdings as get_akshare_institutional_holdings,
    get_limit_up_down_stats as get_akshare_limit_up_down_stats,
    get_pledge_ratio as get_akshare_pledge_ratio,
    AkshareDataError,
)

# Industry classification (akshare-based)
from tradingagents.market_data.industry_classification import (
    get_sw_industry as get_akshare_sw_industry,
    get_industry_peers as get_akshare_industry_peers,
    get_industry_performance as get_akshare_industry_performance,
)

# Tushare Pro news data
from .tushare_news import (
    get_news as get_tushare_news,
    get_global_news as get_tushare_global_news,
    get_cctv_news as get_tushare_cctv_news,
    get_insider_transactions as get_tushare_insider_transactions,
    get_company_news as get_tushare_company_news,
    get_industry_news as get_tushare_industry_news,
    get_policy_news as get_tushare_policy_news,
    TushareDataError,
)

# Tushare Pro core stock and fundamentals data
from .tushare_stock import (
    get_stock as get_tushare_stock,
    get_indicator as get_tushare_indicator,
    get_fundamentals as get_tushare_fundamentals,
    get_balance_sheet as get_tushare_balance_sheet,
    get_cashflow as get_tushare_cashflow,
    get_income_statement as get_tushare_income_statement,
)

# Configuration and routing logic
from .config import get_config


def _call_with_timeout(func, timeout_seconds, *args, **kwargs):
    """Call a function with a timeout. Raises TimeoutError if exceeded."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            raise TimeoutError(f"Data source call timed out after {timeout_seconds}s")


import time


class _CircuitBreaker:
    """Simple in-memory circuit breaker for data vendors.

    Tracks consecutive failures per vendor. After FAILURE_THRESHOLD consecutive
    failures, the vendor is skipped for COOLDOWN_SECONDS.
    """

    FAILURE_THRESHOLD = 3
    COOLDOWN_SECONDS = 60

    def __init__(self):
        self._failures = {}  # vendor -> consecutive failure count
        self._last_failure = {}  # vendor -> timestamp
        self._tripped = {}  # vendor -> bool

    def record_success(self, vendor: str):
        self._failures[vendor] = 0
        self._tripped[vendor] = False

    def record_failure(self, vendor: str):
        now = time.time()
        self._last_failure[vendor] = now
        self._failures[vendor] = self._failures.get(vendor, 0) + 1
        if self._failures[vendor] >= self.FAILURE_THRESHOLD:
            self._tripped[vendor] = True

    def is_open(self, vendor: str) -> bool:
        if not self._tripped.get(vendor):
            return False
        now = time.time()
        last = self._last_failure.get(vendor, 0)
        if now - last > self.COOLDOWN_SECONDS:
            # Cooldown expired, reset
            self._tripped[vendor] = False
            self._failures[vendor] = 0
            return False
        return True


_circuit_breaker = _CircuitBreaker()

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
            "get_pledge_ratio",
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_company_news",
            "get_industry_news",
            "get_policy_news",
            "get_cctv_news",
            "get_insider_transactions",
        ]
    },
    "ashare_market_indicators": {
        "description": "A-share market specific indicators (northbound flow, margin trading, etc.)",
        "tools": [
            "get_north_bound_flow",
            "get_margin_trading",
            "get_limit_up_down_stats",
            "get_dragon_tiger_list",
            "get_block_trade",
            "get_institutional_holdings",
        ]
    },
    "industry_classification": {
        "description": "Industry classification and peer comparison",
        "tools": [
            "get_sw_industry",
            "get_industry_peers",
            "get_industry_performance",
        ]
    }
}

VENDOR_LIST = [
    "akshare",
    "tushare",
    "yfinance",
    "alpha_vantage",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "akshare": get_akshare_stock,
        "tushare": get_tushare_stock,
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "akshare": get_akshare_indicator,
        "tushare": get_tushare_indicator,
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "akshare": get_akshare_fundamentals,
        "tushare": get_tushare_fundamentals,
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "akshare": get_akshare_balance_sheet,
        "tushare": get_tushare_balance_sheet,
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "akshare": get_akshare_cashflow,
        "tushare": get_tushare_cashflow,
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "akshare": get_akshare_income_statement,
        "tushare": get_tushare_income_statement,
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    "get_pledge_ratio": {
        "akshare": get_akshare_pledge_ratio,
    },
    # news_data
    "get_news": {
        "akshare": get_akshare_news,
        "tushare": get_tushare_news,
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "akshare": get_akshare_global_news,
        "tushare": get_tushare_global_news,
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "akshare": get_akshare_insider_transactions,
        "tushare": get_tushare_insider_transactions,
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
    # 三层新闻架构
    "get_company_news": {
        "akshare": get_akshare_company_news,
        "tushare": get_tushare_company_news,
    },
    "get_industry_news": {
        "akshare": get_akshare_industry_news,
        "tushare": get_tushare_industry_news,
    },
    "get_policy_news": {
        "akshare": get_akshare_policy_news,
        "tushare": get_tushare_policy_news,
    },
    # macro_policy_news (backward compat)
    "get_cctv_news": {
        "tushare": get_tushare_cctv_news,
    },
    # ashare_market_indicators
    "get_north_bound_flow": {
        "akshare": get_akshare_north_bound_flow,
    },
    "get_margin_trading": {
        "akshare": get_akshare_margin_trading,
    },
    "get_limit_up_down_stats": {
        "akshare": get_akshare_limit_up_down_stats,
    },
    "get_dragon_tiger_list": {
        "akshare": get_akshare_dragon_tiger_list,
    },
    "get_block_trade": {
        "akshare": get_akshare_block_trade,
    },
    "get_institutional_holdings": {
        "akshare": get_akshare_institutional_holdings,
    },
    # industry_classification
    "get_sw_industry": {
        "akshare": get_akshare_sw_industry,
    },
    "get_industry_peers": {
        "akshare": get_akshare_industry_peers,
    },
    "get_industry_performance": {
        "akshare": get_akshare_industry_performance,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    # Timeout for data source calls
    timeout_sec = get_config().get("tool_timeout", 90)

    def _try_vendor(vendor: str, impl_func):
        """Call a vendor implementation with circuit breaker and timeout."""
        if _circuit_breaker.is_open(vendor):
            raise TimeoutError(f"Circuit breaker open for {vendor}")
        try:
            result = _call_with_timeout(impl_func, timeout_sec, *args, **kwargs)
            _circuit_breaker.record_success(vendor)
            return result
        except (AlphaVantageRateLimitError, TushareNewsDataError, TushareStockDataError, AkshareDataError, TimeoutError):
            _circuit_breaker.record_failure(vendor)
            raise

    # Special handling for news methods with tushare keyword filtering + akshare fallback
    if method in ["get_news", "get_global_news", "get_company_news", "get_industry_news", "get_policy_news"]:
        tushare_result = None
        akshare_result = None

        # Try tushare first if in fallback chain
        if "tushare" in fallback_vendors and "tushare" in VENDOR_METHODS[method]:
            try:
                vendor_impl = VENDOR_METHODS[method]["tushare"]
                impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl
                tushare_result = _try_vendor("tushare", impl_func)

                # Check if tushare indicates fallback needed
                if "_FALLBACK_TO_AKSHARE_" in str(tushare_result):
                    # Call akshare as supplement
                    if "akshare" in VENDOR_METHODS[method]:
                        try:
                            akshare_impl = VENDOR_METHODS[method]["akshare"]
                            akshare_func = akshare_impl[0] if isinstance(akshare_impl, list) else akshare_impl
                            akshare_result = _try_vendor("akshare", akshare_func)

                            # Combine results: tushare data + akshare data
                            if tushare_result and akshare_result:
                                # Extract tushare content (remove fallback marker)
                                tushare_content = tushare_result.replace("_FALLBACK_TO_AKSHARE_", "").strip()

                                # Extract akshare data (remove header if present)
                                akshare_data = akshare_result
                                if akshare_result.startswith("#"):
                                    # Skip akshare header, keep data
                                    lines = akshare_result.split("\n")
                                    data_start = 0
                                    for i, line in enumerate(lines):
                                        if not line.startswith("#") and line.strip():
                                            data_start = i
                                            break
                                    akshare_data = "\n".join(lines[data_start:])

                                # Combine with clear section marker
                                return tushare_content + "\n\n# === AKSHARE SUPPLEMENT (补充数据) ===\n" + akshare_data
                            return akshare_result
                        except (AkshareDataError, Exception):
                            pass
                    # If akshare fails, return tushare result without fallback marker
                    return tushare_result.replace("_FALLBACK_TO_AKSHARE_", "")
                else:
                    # Tushare returned valid data, use it
                    return tushare_result
            except (TushareNewsDataError, TushareDataError, TimeoutError):
                tushare_result = None

        # If tushare not available or failed, try other vendors
        for vendor in fallback_vendors:
            if vendor == "tushare":
                continue  # Already tried
            if vendor not in VENDOR_METHODS[method]:
                continue

            vendor_impl = VENDOR_METHODS[method][vendor]
            impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

            try:
                return _try_vendor(vendor, impl_func)
            except (AlphaVantageRateLimitError, TushareNewsDataError, TushareStockDataError, AkshareDataError, TimeoutError):
                continue

        raise RuntimeError(f"No available vendor for '{method}'")

    # Standard fallback for non-news methods
    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return _try_vendor(vendor, impl_func)
        except (AlphaVantageRateLimitError, TushareNewsDataError, TushareStockDataError, TimeoutError):
            continue  # Rate limits, timeouts and Tushare config errors trigger fallback

    raise RuntimeError(f"No available vendor for '{method}'")