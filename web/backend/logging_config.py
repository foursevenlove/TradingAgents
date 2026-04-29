"""Unified logging configuration for TradingAgents Web UI.

This module provides:
- JSON structured logging for server logs
- Separate log files for different components
- Configurable log levels
- Exception traceback logging
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class JSONFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields if present
        if hasattr(record, "extra_data") and record.extra_data:
            log_data["data"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """Human readable log formatter for console."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        base = f"{timestamp} [{record.levelname}] {record.name}: {record.getMessage()}"

        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)

        return base


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    json_format: bool = False,
) -> logging.Logger:
    """Setup unified logging for the application.

    Args:
        log_dir: Directory for log files
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format for file logs

    Returns:
        Root logger configured with handlers
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger("tradingagents.web")
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # File handler for server logs
    server_log = log_path / "server.log"
    file_handler = logging.FileHandler(server_log, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(JSONFormatter() if json_format else HumanReadableFormatter())
    root_logger.addHandler(file_handler)

    # Console handler for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(HumanReadableFormatter())
    root_logger.addHandler(console_handler)

    # Prevent propagation to root logger (avoid duplicate logs)
    root_logger.propagate = False

    return root_logger


def get_logger(name: str = "tradingagents.web") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding extra data to logs."""

    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.extra_data = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(
                "Exception in context",
                exc_info=(exc_type, exc_val, exc_tb),
                extra={"extra_data": self.extra_data},
            )
        return False  # Don't suppress exception

    def info(self, msg: str, **kwargs):
        data = {**self.extra_data, **kwargs}
        self.logger.info(msg, extra={"extra_data": data})

    def error(self, msg: str, exc: Optional[Exception] = None, **kwargs):
        data = {**self.extra_data, **kwargs}
        if exc:
            self.logger.error(msg, exc_info=exc, extra={"extra_data": data})
        else:
            self.logger.error(msg, extra={"extra_data": data})

    def warning(self, msg: str, **kwargs):
        data = {**self.extra_data, **kwargs}
        self.logger.warning(msg, extra={"extra_data": data})


# Pre-configured logger for quick access
_server_logger: Optional[logging.Logger] = None


def get_server_logger() -> logging.Logger:
    """Get the server logger (initialized lazily)."""
    global _server_logger
    if _server_logger is None:
        _server_logger = get_logger("tradingagents.web.server")
    return _server_logger


def log_exception(exc: Exception, context: Optional[Dict[str, Any]] = None):
    """Log an exception with full traceback and context.

    Args:
        exc: Exception to log
        context: Additional context data
    """
    logger = get_server_logger()
    logger.error(
        f"Exception: {type(exc).__name__}: {str(exc)}",
        exc_info=exc,
        extra={"extra_data": context or {}},
    )


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    error: Optional[str] = None,
):
    """Log an API request.

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        error: Error message if failed
    """
    logger = get_server_logger()
    data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }
    if error:
        data["error"] = error
        logger.warning(f"API {method} {path} failed: {error}", extra={"extra_data": data})
    else:
        logger.info(f"API {method} {path} {status_code} ({duration_ms:.1f}ms)", extra={"extra_data": data})