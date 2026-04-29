"""LangGraph chunk -> SSE event adapter with robust error handling."""
import asyncio
import copy
import json
import logging
import threading
import queue
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

from .models import SSEEvent, EventType, TaskStatus
from .task_manager import get_task_manager
from .config import WEB_CONFIG
from .exceptions import LLMError, LLMTimeoutError, DataSourceError, classify_exception
from .logging_config import get_server_logger, log_exception


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from text."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ── Agent 分析日志 ────────────────────────────────────────────────────────────
# 每次分析写一个独立文件：logs/agent_<task_id[:8]>_<ticker>_<date>.log
# 格式：人类可读的结构化文本，方便后续审查工作流和数据质量

def _get_agent_logger(task_id: str, ticker: str, trade_date: str) -> logging.Logger:
    log_dir = Path(WEB_CONFIG["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    short_id = task_id[:8]
    log_file = log_dir / f"agent_{short_id}_{ticker}_{trade_date}.log"

    logger = logging.getLogger(f"agent.{task_id}")
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.propagate = False  # don't bubble up to root logger / uvicorn
    return logger


# Human-readable labels for each event type
_EVENT_LABELS = {
    EventType.STARTED:        "🚀 分析开始",
    EventType.AGENT_START:    "▶  Agent 启动",
    EventType.AGENT_OUTPUT:   "💬 Agent 输出",
    EventType.AGENT_END:      "✅ Agent 完成",
    EventType.TOOL_CALL:      "🔧 工具调用",
    EventType.TOOL_RESULT:    "📦 工具结果",
    EventType.DEBATE_SPEECH:  "🗣  辩论发言",
    EventType.DEBATE_JUDGE:   "⚖️  辩论裁决",
    EventType.TRADER_PLAN:    "📋 交易计划",
    EventType.FINAL_DECISION: "🎯 最终决策",
    EventType.REPORT_COMPLETE:"📄 报告完成",
    EventType.STATS:          "📊 统计信息",
    EventType.COMPLETED:      "🏁 分析完成",
    EventType.FAILED:         "❌ 分析失败",
}

# Events whose full content is worth logging verbatim
_VERBOSE_EVENTS = {
    EventType.AGENT_OUTPUT,
    EventType.DEBATE_SPEECH,
    EventType.DEBATE_JUDGE,
    EventType.TRADER_PLAN,
    EventType.FINAL_DECISION,
    EventType.REPORT_COMPLETE,
}


def _format_agent_log(event_type: EventType, data: Dict[str, Any]) -> str:
    label = _EVENT_LABELS.get(event_type, event_type.value)
    lines = [f"{label}"]

    if event_type == EventType.STARTED:
        lines.append(f"  股票: {data.get('ticker')}  日期: {data.get('trade_date')}")

    elif event_type == EventType.AGENT_START:
        lines.append(f"  Agent: {data.get('agent_name')}")

    elif event_type == EventType.AGENT_END:
        lines.append(f"  Agent: {data.get('agent_name')}")

    elif event_type == EventType.AGENT_OUTPUT:
        lines.append(f"  Agent: {data.get('agent_name')}  类型: {data.get('msg_type')}")
        content = data.get("content", "")
        for line in content.splitlines():
            lines.append(f"  │ {line}")

    elif event_type == EventType.TOOL_CALL:
        args = data.get("args", {})
        args_str = json.dumps(args, ensure_ascii=False, separators=(",", ":"))
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        lines.append(f"  Agent: {data.get('agent_name')}  工具: {data.get('tool_name')}")
        lines.append(f"  参数: {args_str}")

    elif event_type == EventType.TOOL_RESULT:
        preview = data.get("result_preview", "")
        lines.append(f"  工具: {data.get('tool_name')}  Agent: {data.get('agent_name')}")
        for line in str(preview).splitlines()[:10]:
            lines.append(f"  │ {line}")

    elif event_type == EventType.DEBATE_SPEECH:
        lines.append(f"  [{data.get('side','').upper()}] {data.get('speaker')}  第{data.get('round','')}轮")
        for line in data.get("content", "").splitlines():
            lines.append(f"  │ {line}")

    elif event_type == EventType.DEBATE_JUDGE:
        lines.append(f"  裁判: {data.get('judge')}")
        for line in data.get("decision", "").splitlines():
            lines.append(f"  │ {line}")

    elif event_type == EventType.TRADER_PLAN:
        for line in data.get("content", "").splitlines():
            lines.append(f"  │ {line}")

    elif event_type == EventType.FINAL_DECISION:
        lines.append(f"  信号: {data.get('signal', '?')}")
        for line in data.get("content", "").splitlines():
            lines.append(f"  │ {line}")

    elif event_type == EventType.REPORT_COMPLETE:
        lines.append(f"  报告类型: {data.get('report_type')}")
        for line in data.get("content", "").splitlines()[:20]:
            lines.append(f"  │ {line}")

    elif event_type == EventType.FAILED:
        lines.append(f"  错误: {data.get('error')}")

    lines.append("")
    return "\n".join(lines)


_runners: Dict[str, "AnalysisRunner"] = {}


def get_runner(task_id: str) -> Optional["AnalysisRunner"]:
    return _runners.get(task_id)


def remove_runner(task_id: str):
    _runners.pop(task_id, None)


class AnalysisRunner:
    """Async wrapper around TradingAgentsGraph with event streaming and retry logic."""

    def __init__(
        self,
        task_id: str,
        ticker: str,
        trade_date: str,
        analysts: list = None,
        config_override: Optional[Dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.ticker = ticker
        self.trade_date = trade_date
        self.analysts = analysts or ["market", "social", "news", "fundamentals"]
        self.config = self._build_config(config_override)
        self.queue: asyncio.Queue = asyncio.Queue()
        self.state: Dict[str, Any] = {}
        self._cancelled = False
        self._seen_agents: set = set()
        self._last_debate_count = 0
        self._last_risk_count = 0
        self._judge_decision_sent = False
        self._risk_judge_sent = False
        self._final_decision_sent = False
        self._agent_logger = _get_agent_logger(task_id, ticker, trade_date)

    def _build_config(self, override: Optional[Dict]) -> Dict[str, Any]:
        config = copy.deepcopy(DEFAULT_CONFIG)
        if override:
            for k, v in override.items():
                if isinstance(v, dict) and isinstance(config.get(k), dict):
                    config[k].update(v)
                else:
                    config[k] = v
        return config

    def cancel(self):
        self._cancelled = True

    async def run(self):
        """Run analysis with retry logic and proper exception handling."""
        _logger = get_server_logger()

        # Retry configuration
        MAX_RETRIES = 3
        RETRY_DELAY = 5  # seconds
        SILENCE_TIMEOUT = 600  # seconds

        for attempt in range(MAX_RETRIES):
            try:
                _logger.info(f"Starting analysis attempt {attempt + 1}/{MAX_RETRIES} for {self.ticker}")

                graph = TradingAgentsGraph(
                    selected_analysts=self.analysts,
                    config=self.config,
                )
                init_state = graph.propagator.create_initial_state(
                    self.ticker, self.trade_date
                )
                stream_config = {"recursion_limit": self.config.get("max_recur_limit", 100)}

                await self._emit(EventType.STARTED, {"ticker": self.ticker, "trade_date": self.trade_date})
                get_task_manager().update_status(self.task_id, TaskStatus.RUNNING)

                # Bridge: background thread -> asyncio.Queue
                loop = asyncio.get_event_loop()
                async_queue: asyncio.Queue = asyncio.Queue()

                def run_graph_sync():
                    try:
                        for chunk in graph.graph.stream(init_state, stream_mode="updates", config=stream_config):
                            if self._cancelled:
                                loop.call_soon_threadsafe(async_queue.put_nowait, ("cancelled", None))
                                return
                            loop.call_soon_threadsafe(async_queue.put_nowait, ("chunk", chunk))
                        loop.call_soon_threadsafe(async_queue.put_nowait, ("done", None))
                    except Exception as e:
                        _logger.error(f"Graph execution error: {type(e).__name__}: {str(e)}")
                        classified = classify_exception(e)
                        loop.call_soon_threadsafe(async_queue.put_nowait, ("error", {
                            "type": classified.error_code,
                            "message": classified.user_message,
                            "detail": str(e),
                        }))

                thread = threading.Thread(target=run_graph_sync, daemon=True)
                thread.start()

                # Drain queue
                while True:
                    try:
                        item_type, item_data = await asyncio.wait_for(async_queue.get(), timeout=SILENCE_TIMEOUT)
                    except asyncio.TimeoutError:
                        _logger.warning(f"Task timeout after {SILENCE_TIMEOUT}s, attempt {attempt + 1}")
                        if attempt < MAX_RETRIES - 1:
                            await self._emit(EventType.FAILED, {
                                "error": f"任务超时，正在重试 ({attempt + 2}/{MAX_RETRIES})...",
                                "is_retry": True,
                            })
                            await asyncio.sleep(RETRY_DELAY)
                            continue
                        else:
                            raise LLMTimeoutError(detail=f"任务超时：{SILENCE_TIMEOUT // 60} 分钟内无响应")

                    if item_type == "chunk":
                        await self._process_chunk(item_data)
                    elif item_type == "done":
                        break
                    elif item_type == "cancelled":
                        get_task_manager().update_status(self.task_id, TaskStatus.CANCELLED)
                        await self._emit(EventType.FAILED, {"error": "分析已取消"})
                        return
                    elif item_type == "error":
                        error_info = item_data
                        _logger.error(f"Analysis error: {error_info['type']} - {error_info['detail']}")

                        if error_info["type"] in ["LLM_ERROR", "LLM_TIMEOUT"] and attempt < MAX_RETRIES - 1:
                            await self._emit(EventType.FAILED, {
                                "error": f"{error_info['message']}，正在重试 ({attempt + 2}/{MAX_RETRIES})...",
                                "is_retry": True,
                            })
                            await asyncio.sleep(RETRY_DELAY)
                            continue
                        else:
                            raise Exception(error_info["detail"])

                thread.join(timeout=2.0)

                if not self._cancelled:
                    final_state = self.state
                    signal = ""
                    try:
                        raw_decision = final_state.get("final_trade_decision", "")
                        clean_decision = _strip_think_blocks(raw_decision)
                        signal = graph.process_signal(clean_decision)
                        signal = _strip_think_blocks(signal).strip().upper()
                    except Exception as e:
                        _logger.warning(f"Signal processing error: {e}")
                        signal = "UNKNOWN"

                    if not self._final_decision_sent and final_state.get("final_trade_decision"):
                        await self._emit(EventType.FINAL_DECISION, {
                            "content": final_state["final_trade_decision"],
                            "signal": signal,
                        })

                    await self._emit(EventType.COMPLETED, {"task_id": self.task_id})
                    get_task_manager().update_status(self.task_id, TaskStatus.COMPLETED)

                    result = self._build_result(final_state)
                    get_task_manager().set_result(self.task_id, result, signal)

                    _logger.info(f"Analysis completed successfully for {self.ticker}")
                    return  # Success

            except LLMTimeoutError as e:
                _logger.error(f"LLM timeout on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await self._emit(EventType.FAILED, {
                        "error": f"AI 模型响应超时，正在重试 ({attempt + 2}/{MAX_RETRIES})...",
                        "is_retry": True,
                    })
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    error_msg = e.user_message
                    await self._emit(EventType.FAILED, {"error": error_msg})
                    get_task_manager().update_status(self.task_id, TaskStatus.FAILED, error=error_msg)
                    log_exception(e, context={"task_id": self.task_id, "ticker": self.ticker, "attempts": attempt + 1})

            except LLMError as e:
                _logger.error(f"LLM error on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await self._emit(EventType.FAILED, {
                        "error": f"{e.user_message}，正在重试 ({attempt + 2}/{MAX_RETRIES})...",
                        "is_retry": True,
                    })
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    error_msg = e.user_message
                    await self._emit(EventType.FAILED, {"error": error_msg})
                    get_task_manager().update_status(self.task_id, TaskStatus.FAILED, error=error_msg)
                    log_exception(e, context={"task_id": self.task_id, "ticker": self.ticker, "attempts": attempt + 1})

            except DataSourceError as e:
                _logger.error(f"Data source error: {e}")
                error_msg = e.user_message
                await self._emit(EventType.FAILED, {"error": error_msg})
                get_task_manager().update_status(self.task_id, TaskStatus.FAILED, error=error_msg)
                log_exception(e, context={"task_id": self.task_id, "ticker": self.ticker})
                break

            except Exception as e:
                _logger.error(f"Unexpected error on attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
                classified = classify_exception(e)

                if classified.error_code in ["LLM_ERROR", "LLM_TIMEOUT"] and attempt < MAX_RETRIES - 1:
                    await self._emit(EventType.FAILED, {
                        "error": f"{classified.user_message}，正在重试 ({attempt + 2}/{MAX_RETRIES})...",
                        "is_retry": True,
                    })
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    error_msg = classified.user_message
                    await self._emit(EventType.FAILED, {"error": error_msg})
                    get_task_manager().update_status(self.task_id, TaskStatus.FAILED, error=error_msg)
                    log_exception(e, context={
                        "task_id": self.task_id,
                        "ticker": self.ticker,
                        "attempts": attempt + 1,
                        "classified_as": classified.error_code,
                    })
                    break

            finally:
                remove_runner(self.task_id)

    async def _process_chunk(self, chunk: Dict[str, Any]):
        for node_name, node_data in chunk.items():
            if not isinstance(node_data, dict):
                continue

            if node_name.startswith("tools_"):
                continue

            debate_agent_nodes = [
                "Bull Researcher", "Bear Researcher", "Research Manager",
                "Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Risk Judge",
                "Trader",
            ]

            if node_name in debate_agent_nodes:
                if node_name == "Research Manager" and node_name not in self._seen_agents:
                    if "investment_debate_state" in node_data:
                        self._seen_agents.add(node_name)
                        await self._emit(EventType.AGENT_START, {"agent_name": node_name})
                elif node_name == "Risk Judge" and node_name not in self._seen_agents:
                    if "risk_debate_state" in node_data or "final_trade_decision" in node_data:
                        self._seen_agents.add(node_name)
                        await self._emit(EventType.AGENT_START, {"agent_name": node_name})

            for key, value in node_data.items():
                if key != "messages":
                    self.state[key] = value

            if node_name.startswith("Msg Clear"):
                raw = node_name.replace("Msg Clear ", "")
                analyst_name = f"{raw} Analyst"
                await self._emit(EventType.AGENT_END, {"agent_name": analyst_name})
                continue

            messages = node_data.get("messages", [])
            if messages:
                if "messages" not in self.state:
                    self.state["messages"] = []
                self.state["messages"].extend(messages)
                await self._handle_messages(node_name, messages)

            if "investment_debate_state" in node_data:
                await self._handle_invest_debate(node_data["investment_debate_state"])

            if "risk_debate_state" in node_data:
                await self._handle_risk_debate(node_data["risk_debate_state"])

            if "trader_investment_plan" in node_data and node_data["trader_investment_plan"]:
                if "Trader" not in self._seen_agents:
                    self._seen_agents.add("Trader")
                    await self._emit(EventType.AGENT_START, {"agent_name": "Trader"})
                await self._emit(EventType.TRADER_PLAN, {
                    "content": node_data["trader_investment_plan"],
                })

            if "final_trade_decision" in node_data and node_data["final_trade_decision"]:
                if not self._final_decision_sent:
                    self._final_decision_sent = True
                    if "Trader" not in self._seen_agents:
                        self._seen_agents.add("Trader")
                        await self._emit(EventType.AGENT_START, {"agent_name": "Trader"})
                    await self._emit(EventType.FINAL_DECISION, {
                        "content": node_data["final_trade_decision"],
                    })
                    await self._emit(EventType.AGENT_END, {"agent_name": "Trader"})

            for report_key in ["market_report", "sentiment_report", "news_report", "fundamentals_report"]:
                if report_key in node_data and node_data[report_key]:
                    content = node_data[report_key]
                    preview = content[:500] + "..." if len(content) > 500 else content
                    await self._emit(EventType.REPORT_COMPLETE, {
                        "report_type": report_key,
                        "content": preview,
                    })

    async def _handle_messages(self, node_name: str, messages: list):
        if node_name not in self._seen_agents:
            self._seen_agents.add(node_name)
            await self._emit(EventType.AGENT_START, {"agent_name": node_name})

        last_msg = messages[-1]
        msg_type = type(last_msg).__name__

        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            for tc in last_msg.tool_calls:
                await self._emit(EventType.TOOL_CALL, {
                    "agent_name": node_name,
                    "tool_name": tc.get("name", "unknown"),
                    "args": tc.get("args", {}),
                })

        if msg_type == "ToolMessage" and hasattr(last_msg, "content"):
            content = str(last_msg.content) if last_msg.content else ""
            preview = content[:300] + "..." if len(content) > 300 else content
            parent_agent = self._infer_parent_agent(node_name)
            await self._emit(EventType.TOOL_RESULT, {
                "agent_name": parent_agent,
                "tool_name": getattr(last_msg, "name", node_name),
                "result_preview": preview,
            })

        if hasattr(last_msg, "content") and last_msg.content and msg_type != "ToolMessage":
            await self._emit(EventType.AGENT_OUTPUT, {
                "agent_name": node_name,
                "content": str(last_msg.content),
                "msg_type": msg_type,
            })

    def _infer_parent_agent(self, node_name: str) -> str:
        if node_name.startswith("tools_"):
            analyst_type = node_name.replace("tools_", "")
            return f"{analyst_type.capitalize()} Analyst"
        return node_name

    async def _handle_invest_debate(self, debate: Dict[str, Any]):
        judge = debate.get("judge_decision", "")
        if judge and not self._judge_decision_sent:
            self._judge_decision_sent = True
            for name in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
                if name not in self._seen_agents:
                    self._seen_agents.add(name)
                    await self._emit(EventType.AGENT_START, {"agent_name": name})
            await self._emit(EventType.DEBATE_JUDGE, {
                "judge": "Research Manager",
                "decision": judge,
            })
            for name in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
                await self._emit(EventType.AGENT_END, {"agent_name": name})
            return

        count = debate.get("count", 0)
        if count <= self._last_debate_count:
            return
        self._last_debate_count = count

        current = debate.get("current_response", "")
        if current.startswith("看涨"):
            agent_name = "Bull Researcher"
            if agent_name not in self._seen_agents:
                self._seen_agents.add(agent_name)
                await self._emit(EventType.AGENT_START, {"agent_name": agent_name})
            content = self._extract_last_line(debate.get("bull_history", ""))
            await self._emit(EventType.DEBATE_SPEECH, {
                "side": "bull",
                "speaker": "Bull Researcher",
                "content": content,
                "round": (count + 1) // 2,
            })
        elif current.startswith("看跌"):
            agent_name = "Bear Researcher"
            if agent_name not in self._seen_agents:
                self._seen_agents.add(agent_name)
                await self._emit(EventType.AGENT_START, {"agent_name": agent_name})
            content = self._extract_last_line(debate.get("bear_history", ""))
            await self._emit(EventType.DEBATE_SPEECH, {
                "side": "bear",
                "speaker": "Bear Researcher",
                "content": content,
                "round": count // 2,
            })

    async def _handle_risk_debate(self, debate: Dict[str, Any]):
        judge = debate.get("judge_decision", "")
        if judge and not self._risk_judge_sent:
            self._risk_judge_sent = True
            for name in ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Risk Judge"]:
                if name not in self._seen_agents:
                    self._seen_agents.add(name)
                    await self._emit(EventType.AGENT_START, {"agent_name": name})
            await self._emit(EventType.DEBATE_JUDGE, {
                "judge": "Risk Manager",
                "decision": judge,
            })
            for name in ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Risk Judge"]:
                await self._emit(EventType.AGENT_END, {"agent_name": name})
            return

        count = debate.get("count", 0)
        if count <= self._last_risk_count:
            return
        self._last_risk_count = count

        speaker = debate.get("latest_speaker", "")
        if speaker.startswith("Aggressive"):
            side, content = "aggressive", debate.get("current_aggressive_response", "")
            agent_name = "Aggressive Analyst"
        elif speaker.startswith("Conservative"):
            side, content = "conservative", debate.get("current_conservative_response", "")
            agent_name = "Conservative Analyst"
        elif speaker.startswith("Neutral"):
            side, content = "neutral", debate.get("current_neutral_response", "")
            agent_name = "Neutral Analyst"
        else:
            return

        if agent_name not in self._seen_agents:
            self._seen_agents.add(agent_name)
            await self._emit(EventType.AGENT_START, {"agent_name": agent_name})

        await self._emit(EventType.DEBATE_SPEECH, {
            "side": side,
            "speaker": speaker,
            "content": content,
            "round": (count - 1) // 3 + 1,
        })

    def _extract_last_line(self, text: str) -> str:
        if not text:
            return ""
        markers = ["看涨分析师：", "看跌分析师：", "激进风控：", "保守风控：", "中性风控："]
        last_marker_pos = -1
        for marker in markers:
            pos = text.rfind(marker)
            if pos > last_marker_pos:
                last_marker_pos = pos

        if last_marker_pos >= 0:
            return text[last_marker_pos:].strip()
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paragraphs[-1] if paragraphs else ""

    async def _emit(self, event_type: EventType, data: Dict[str, Any]):
        event = SSEEvent(type=event_type, task_id=self.task_id, data=data)
        await self.queue.put(event)
        get_task_manager().save_event(self.task_id, event_type.value, data)
        try:
            self._agent_logger.info(_format_agent_log(event_type, data))
        except Exception:
            pass

    def _build_result(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ticker": state.get("company_of_interest"),
            "trade_date": state.get("trade_date"),
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "investment_debate_state": {
                "bull_history": state.get("investment_debate_state", {}).get("bull_history", ""),
                "bear_history": state.get("investment_debate_state", {}).get("bear_history", ""),
                "judge_decision": state.get("investment_debate_state", {}).get("judge_decision", ""),
            },
            "trader_investment_plan": state.get("trader_investment_plan", ""),
            "risk_debate_state": {
                "aggressive_history": state.get("risk_debate_state", {}).get("aggressive_history", ""),
                "conservative_history": state.get("risk_debate_state", {}).get("conservative_history", ""),
                "neutral_history": state.get("risk_debate_state", {}).get("neutral_history", ""),
                "judge_decision": state.get("risk_debate_state", {}).get("judge_decision", ""),
            },
            "final_trade_decision": state.get("final_trade_decision", ""),
            "investment_plan": state.get("investment_plan", ""),
        }


async def start_analysis(
    task_id: str,
    ticker: str,
    trade_date: str,
    analysts: list = None,
    config_override: Optional[Dict[str, Any]] = None,
) -> AnalysisRunner:
    runner = AnalysisRunner(task_id, ticker, trade_date, analysts, config_override)
    _runners[task_id] = runner
    asyncio.create_task(runner.run())
    return runner