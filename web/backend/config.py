"""Web UI configuration."""
import os
from pathlib import Path

_BASE_DIR = Path(__file__).parent.parent

WEB_CONFIG = {
    "host": os.getenv("TRADINGAGENTS_WEB_HOST", "0.0.0.0"),
    "port": int(os.getenv("TRADINGAGENTS_WEB_PORT", "8000")),
    "db_path": os.getenv("TRADINGAGENTS_WEB_DB", str(_BASE_DIR / "tasks.db")),
    "log_dir": os.getenv("TRADINGAGENTS_WEB_LOG_DIR", str(_BASE_DIR / "logs")),
    "frontend_dist": str(_BASE_DIR / "frontend" / "dist"),
}
