"""TradingAgents validation adapter for recommendation candidates."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class TradingAgentsValidationResult:
    code: str
    decision: str
    confidence: float
    market_summary: str = ""
    news_summary: str = ""
    risk_summary: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "decision": self.decision,
            "confidence": self.confidence,
            "market_summary": self.market_summary,
            "news_summary": self.news_summary,
            "risk_summary": self.risk_summary,
            "reason": self.reason,
        }


def _first_text(state: Dict[str, Any], *keys: str, limit: int = 500) -> str:
    for key in keys:
        value = state.get(key)
        if value:
            if isinstance(value, dict):
                value = value.get("judge_decision") or value.get("final_trade_decision") or value
            return str(value)[:limit]
    return ""


def normalize_graph_result(graph_result: Any, stock_code: str) -> TradingAgentsValidationResult:
    """Normalize TradingAgentsGraph output to a stable validation result."""
    final_state = graph_result
    signal = ""

    if isinstance(graph_result, tuple):
        if len(graph_result) >= 1:
            final_state = graph_result[0]
        if len(graph_result) >= 2:
            signal = str(graph_result[1] or "")

    if not isinstance(final_state, dict):
        final_state = {}

    decision = (
        signal
        or str(final_state.get("final_decision") or "")
        or str(final_state.get("decision") or "")
        or "UNKNOWN"
    ).strip().upper()

    try:
        confidence = float(final_state.get("final_decision_confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    return TradingAgentsValidationResult(
        code=stock_code,
        decision=decision,
        confidence=confidence,
        market_summary=_first_text(final_state, "market_analyst_report", "market_report"),
        news_summary=_first_text(final_state, "news_analyst_report", "news_report"),
        risk_summary=_first_text(final_state, "risk_manager_decision", "risk_debate_state"),
        reason=f"TradingAgents验证: {decision}",
    )


class TradingAgentsValidator:
    """Thin adapter around TradingAgentsGraph for recommendation workflows."""

    def __init__(self, selected_analysts, config=None, debug: bool = False):
        self.selected_analysts = selected_analysts
        self.config = config
        self.debug = debug

    def validate(self, stock_code: str, trade_date: str) -> Dict[str, Any]:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        graph = TradingAgentsGraph(
            selected_analysts=self.selected_analysts,
            debug=self.debug,
            config=self.config,
        )
        graph_result = graph.propagate(stock_code, trade_date)
        return normalize_graph_result(graph_result, stock_code).to_dict()
