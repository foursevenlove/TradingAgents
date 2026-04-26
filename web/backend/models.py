"""Pydantic models for the TradingAgents Web UI API."""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class EventType(str, Enum):
    STARTED = "started"
    AGENT_START = "agent_start"
    AGENT_OUTPUT = "agent_output"
    AGENT_END = "agent_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DEBATE_SPEECH = "debate_speech"
    DEBATE_JUDGE = "debate_judge"
    TRADER_PLAN = "trader_plan"
    FINAL_DECISION = "final_decision"
    REPORT_COMPLETE = "report_complete"
    STATS = "stats"
    COMPLETED = "completed"
    FAILED = "failed"


class SSEEvent(BaseModel):
    type: EventType
    task_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        payload = self.model_dump_json(exclude={"type"})
        return f"event: {self.type}\ndata: {payload}\n\n"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="股票代码，如 600000.SH")
    trade_date: Optional[str] = Field(None, description="分析日期，默认今天")
    analysts: List[str] = Field(
        default=["market", "social", "news", "fundamentals"],
        description="启用的分析师类型"
    )
    max_debate_rounds: Optional[int] = Field(None, description="多空辩论轮数")
    max_risk_discuss_rounds: Optional[int] = Field(None, description="风险讨论轮数")
    data_vendors: Optional[Dict[str, str]] = Field(None, description="数据源配置覆盖")


class TaskSummary(BaseModel):
    task_id: str
    ticker: str
    trade_date: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    signal: Optional[str] = None


class TaskDetail(BaseModel):
    task_id: str
    ticker: str
    trade_date: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    signal: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)


class SystemConfig(BaseModel):
    version: str = "0.2.1"
    llm_provider: str
    deep_think_llm: str
    quick_think_llm: str
    default_analysts: List[str]
    default_debate_rounds: int
    default_risk_rounds: int


class HistoryResponse(BaseModel):
    tasks: List[TaskSummary]
    total: int
