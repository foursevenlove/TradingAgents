import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "minimax",
    "deep_think_llm": "MiniMax-M2.7",
    "quick_think_llm": "MiniMax-M2.5",
    "backend_url": "https://api.minimaxi.com/v1",
    "temperature": 0.1,                 # Lower = more deterministic, better instruction following
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    # Debate and discussion settings
    "max_debate_rounds": 2,                   # Bull vs Bear debate rounds (more rounds = deeper analysis)
    "max_risk_discuss_rounds": 2,             # Risk debate rounds (Aggressive/Conservative/Neutral)
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "tushare,akshare",          # tushare primary (stable API), akshare fallback
        "technical_indicators": "tushare,akshare",      # tushare primary, akshare fallback
        "fundamental_data": "tushare,akshare",          # tushare primary (requires 2000积分), akshare fallback
        "news_data": "tushare,akshare",                  # tushare primary (supports date filtering), akshare fallback
        "ashare_market_indicators": "akshare",           # A-share specific: northbound flow, margin, etc.
        "industry_classification": "akshare",            # Industry classification and peer comparison
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}
