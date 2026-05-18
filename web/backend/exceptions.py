"""Unified exception classes for TradingAgents Web UI.

This module provides:
- Custom exception hierarchy with user-friendly messages
- Structured error response format for API responses
- Exception classification for proper handling
"""
import traceback
from typing import Optional, Dict, Any


class ErrorResponse:
    """Standard API error response format."""

    def __init__(
        self,
        error_code: str,
        message: str,
        detail: Optional[str] = None,
        status_code: int = 500,
    ):
        self.error_code = error_code
        self.message = message  # User-friendly message
        self.detail = detail    # Technical detail (for logs/debugging)
        self.status_code = status_code

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }

    def log_detail(self) -> str:
        """Format for logging (includes full detail)."""
        return f"[{self.error_code}] {self.message} | Detail: {self.detail}"


class TradingAgentsError(Exception):
    """Base exception for all TradingAgents errors.

    Attributes:
        error_code: Unique identifier for this error type
        user_message: User-friendly message (shown in UI)
        detail: Technical detail (logged, not shown to user)
        status_code: HTTP status code to return
    """
    error_code: str = "INTERNAL_ERROR"
    user_message: str = "服务内部错误，请稍后重试"
    status_code: int = 500

    def __init__(
        self,
        detail: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        self.detail = detail or str(self)
        self.user_message = user_message or self.user_message
        super().__init__(self.detail)

    def to_response(self) -> ErrorResponse:
        """Convert to standard error response."""
        return ErrorResponse(
            error_code=self.error_code,
            message=self.user_message,
            detail=self.detail,
            status_code=self.status_code,
        )


class TaskNotFoundError(TradingAgentsError):
    """Task does not exist."""
    error_code = "TASK_NOT_FOUND"
    user_message = "任务不存在，可能已被删除或 ID 错误"
    status_code = 404


class TaskNotRunningError(TradingAgentsError):
    """Task is not in running state."""
    error_code = "TASK_NOT_RUNNING"
    user_message = "任务不在运行状态，无法执行此操作"
    status_code = 400


class LLMError(TradingAgentsError):
    """LLM API call failed."""
    error_code = "LLM_ERROR"
    user_message = "AI 模型服务暂时不可用，请稍后重试"
    status_code = 500

    def __init__(
        self,
        detail: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        msg = f"LLM API 调用失败 (provider: {provider})" if provider else "LLM API 调用失败"
        super().__init__(detail=detail or msg)


class LLMTimeoutError(LLMError):
    """LLM API call timed out."""
    error_code = "LLM_TIMEOUT"
    user_message = "AI 模型响应超时，请稍后重试"


class LLMAccountError(LLMError):
    """LLM account cannot serve requests due to billing/quota status."""
    error_code = "LLM_ACCOUNT_ERROR"
    user_message = "AI 模型账号不可用，请检查额度或欠费状态"


class DataSourceError(TradingAgentsError):
    """Data source API call failed."""
    error_code = "DATA_SOURCE_ERROR"
    user_message = "数据获取失败，可能是数据源暂时不可用"
    status_code = 500

    def __init__(
        self,
        detail: Optional[str] = None,
        vendor: Optional[str] = None,
        method: Optional[str] = None,
    ):
        msg_parts = []
        if method:
            msg_parts.append(f"method: {method}")
        if vendor:
            msg_parts.append(f"vendor: {vendor}")
        msg = f"数据源调用失败 ({', '.join(msg_parts)})" if msg_parts else "数据源调用失败"
        super().__init__(detail=detail or msg)


class DataSourceTimeoutError(DataSourceError):
    """Data source API call timed out."""
    error_code = "DATA_SOURCE_TIMEOUT"
    user_message = "数据获取超时，请稍后重试"


class ValidationError(TradingAgentsError):
    """Request validation failed."""
    error_code = "VALIDATION_ERROR"
    user_message = "请求参数无效"
    status_code = 400


class SchedulerError(TradingAgentsError):
    """Scheduler operation failed."""
    error_code = "SCHEDULER_ERROR"
    user_message = "定时任务调度失败"
    status_code = 500


class WatchlistError(TradingAgentsError):
    """Watchlist operation failed."""
    error_code = "WATCHLIST_ERROR"
    user_message = "自选股操作失败"
    status_code = 400


class StockNotFoundError(TradingAgentsError):
    """Stock not found in watchlist."""
    error_code = "STOCK_NOT_FOUND"
    user_message = "股票不存在"
    status_code = 404


class BatchError(TradingAgentsError):
    """Batch analysis operation failed."""
    error_code = "BATCH_ERROR"
    user_message = "批量分析操作失败"
    status_code = 500


class EmptyWatchlistError(BatchError):
    """Watchlist is empty."""
    error_code = "EMPTY_WATCHLIST"
    user_message = "自选股列表为空，请先添加自选股"
    status_code = 400


def classify_exception(exc: Exception) -> TradingAgentsError:
    """Classify a generic exception into appropriate TradingAgentsError.

    This function analyzes exception types and messages to create
    appropriate TradingAgentsError instances.
    """
    exc_str = str(exc)
    exc_type = type(exc).__name__
    exc_lower = exc_str.lower()
    exc_type_lower = exc_type.lower()

    timeout_indicators = [
        "timeout", "timed out", "readtimeout", "apitimeouterror",
    ]

    if any(ind in exc_lower or ind in exc_type_lower for ind in timeout_indicators):
        llm_timeout_types = ["apitimeouterror", "readtimeout"]
        if any(ind in exc_type_lower for ind in llm_timeout_types):
            return LLMTimeoutError(detail=exc_str)

    account_indicators = [
        "arrearage", "overdue-payment", "insufficient_quota",
        "exceeded your current quota", "good standing",
    ]
    if any(ind in exc_lower for ind in account_indicators):
        return LLMAccountError(detail=exc_str)

    # Check for LLM-related errors
    llm_indicators = [
        "api_key", "rate_limit", "model", "token", "llm",
        "openai", "anthropic", "minimax", "dashscope", "alibaba",
        "aliyun_coding_plan", "coding_plan",
        "connection refused", "timeout", "503", "502", "429",
        "invalid_request_error", "invalid_parameter_error",
        "range of input length", "input length",
        "api connection", "apiconnectionerror", "connection error",
        "connection reset by peer",
    ]
    if any(ind in exc_lower or ind in exc_type_lower for ind in llm_indicators):
        if any(ind in exc_lower or ind in exc_type_lower for ind in timeout_indicators):
            return LLMTimeoutError(detail=exc_str)
        return LLMError(detail=exc_str)

    # Check for data source errors
    data_indicators = [
        "tushare", "akshare", "yfinance", "alpha_vantage",
        "data", "stock", "price", "indicator", "news",
        "vendor", "route_to_vendor",
    ]
    if any(ind in exc_lower for ind in data_indicators):
        if any(ind in exc_lower or ind in exc_type_lower for ind in timeout_indicators):
            return DataSourceTimeoutError(detail=exc_str)
        return DataSourceError(detail=exc_str)

    # Check for timeout specifically
    if any(ind in exc_lower or ind in exc_type_lower for ind in timeout_indicators):
        return TradingAgentsError(
            detail=exc_str,
            user_message="操作超时，请稍后重试",
        )

    # Default: generic internal error
    return TradingAgentsError(detail=exc_str)


def get_exception_traceback(exc: Exception) -> str:
    """Get full traceback string for logging."""
    return traceback.format_exception(type(exc), exc, exc.__traceback__)
