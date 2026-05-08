"""Web UI configuration."""
import os
from pathlib import Path

_BASE_DIR = Path(__file__).parent.parent

def _parse_cors_origins():
    raw = os.getenv("TRADINGAGENTS_CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["*"]  # Default: allow all (development only)


WEB_CONFIG = {
    "host": os.getenv("TRADINGAGENTS_WEB_HOST", "0.0.0.0"),
    "port": int(os.getenv("TRADINGAGENTS_WEB_PORT", "8000")),
    "db_path": os.getenv("TRADINGAGENTS_WEB_DB", str(_BASE_DIR / "tasks.db")),
    "log_dir": os.getenv("TRADINGAGENTS_WEB_LOG_DIR", str(_BASE_DIR / "logs")),
    "frontend_dist": str(_BASE_DIR / "frontend" / "dist"),
    "cors_origins": _parse_cors_origins(),
    "api_key": os.getenv("TRADINGAGENTS_API_KEY", ""),
}
