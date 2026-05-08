import os
from tradingagents.llm_clients.validators import get_default_settings

# Load default LLM settings from llm_models.json
_llm_defaults = get_default_settings()

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),

    # ── LLM Provider Settings (from llm_models.json) ───────────────
    "llm_provider": _llm_defaults.get("provider", "minimax"),
    "deep_think_llm": _llm_defaults.get("deep_think_llm", "MiniMax-M2.7"),
    "quick_think_llm": _llm_defaults.get("quick_think_llm", "MiniMax-M2.5"),
    "temperature": _llm_defaults.get("temperature", 0.1),
    "backend_url": None,

    # Provider-specific thinking/reasoning settings
    "enable_thinking": _llm_defaults.get("enable_thinking", False),
    "max_thinking_tokens": _llm_defaults.get("max_thinking_tokens"),  # Limit reasoning output length
    "openai_reasoning_effort": _llm_defaults.get("openai_reasoning_effort"),
    "google_thinking_level": _llm_defaults.get("google_thinking_level"),

    # ── Debate and Discussion Settings ─────────────────────────────
    "max_debate_rounds": 2,
    "max_risk_discuss_rounds": 2,
    "max_recur_limit": 100,

    # ── Data Vendor Configuration ──────────────────────────────────
    "data_vendors": {
        "core_stock_apis": "tushare,akshare",
        "technical_indicators": "tushare,akshare",
        "fundamental_data": "tushare,akshare",
        "news_data": "tushare,akshare",
        "ashare_market_indicators": "akshare",
        "industry_classification": "akshare",
    },
    "tool_vendors": {},

    # ── Timeout Configuration ──────────────────────────────────────
    "tool_timeout": 90,  # seconds for single tool call (data fetch)
    "llm_timeout": {
        "minimax": 300,
        "alibaba": 180,
        "openai": 120,
        "anthropic": 120,
        "google": 120,
        "default": 120,
    },

    # ── Concurrency Configuration ──────────────────────────────────
    "max_concurrent_tasks": 4,  # max concurrent analysis tasks globally
}