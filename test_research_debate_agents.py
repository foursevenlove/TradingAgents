import pytest

from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator
from web.backend.models import AnalyzeRequest


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("Response", (), {"content": self.content})()


class FakeMemory:
    def get_memories(self, current_situation, n_matches=1):
        return []


def _base_state():
    state = Propagator().create_initial_state("600000.SH", "2026-05-18")
    state.update(
        {
            "market_report": "市场数据\n| 指标 | 数值 |\n|---|---|\n| 当前价 | 10元 |",
            "sentiment_report": "舆情数据\n| 指标 | 数值 |\n|---|---|\n| 情绪 | 中性 |",
            "news_report": "新闻数据\n| 指标 | 数值 |\n|---|---|\n| 新闻 | 无重大利空 |",
            "fundamentals_report": "基本面数据\n| 指标 | 数值 |\n|---|---|\n| ROE | 8% |",
        }
    )
    return state


def test_bull_first_turn_records_structured_state_and_prompt():
    llm = FakeLLM("基于市场研究报告显示当前价10元，建议投资该股票。")
    node = create_bull_researcher(llm, FakeMemory())

    result = node(_base_state())
    debate = result["investment_debate_state"]

    assert debate["latest_speaker"] == "bull"
    assert debate["count"] == 1
    assert debate["debate_turns"] == [
        {
            "speaker": "bull",
            "label": "看涨分析师",
            "round": 1,
            "content": llm.content,
        }
    ]
    assert "这是首轮发言" in llm.prompts[0]
    assert "暂无看跌论点" in llm.prompts[0]


def test_bear_turn_uses_structured_state_and_router_uses_latest_speaker():
    state = _base_state()
    state["investment_debate_state"].update(
        {
            "current_response": "看涨分析师：已有看涨论点",
            "latest_speaker": "bull",
            "count": 1,
            "debate_turns": [
                {
                    "speaker": "bull",
                    "label": "看涨分析师",
                    "round": 1,
                    "content": "已有看涨论点",
                }
            ],
        }
    )

    assert ConditionalLogic(max_debate_rounds=2).should_continue_debate(state) == "Bear Researcher"

    llm = FakeLLM("基于基本面报告显示ROE为8%，不建议投资该股票。")
    result = create_bear_researcher(llm, FakeMemory())(state)
    debate = result["investment_debate_state"]

    assert debate["latest_speaker"] == "bear"
    assert debate["count"] == 2
    assert debate["debate_turns"][-1]["speaker"] == "bear"
    assert debate["debate_turns"][-1]["round"] == 1
    assert "最新看涨论点" in llm.prompts[0]


def test_research_manager_receives_full_debate_and_data_first_instruction():
    state = _base_state()
    state["investment_debate_state"].update(
        {
            "bull_history": "\n看涨分析师：第一轮看涨",
            "bear_history": "\n看跌分析师：第一轮看跌",
            "history": "\n看涨分析师：第一轮看涨\n看跌分析师：第一轮看跌",
            "count": 2,
            "debate_turns": [
                {
                    "speaker": "bull",
                    "label": "看涨分析师",
                    "round": 1,
                    "content": "第一轮看涨",
                },
                {
                    "speaker": "bear",
                    "label": "看跌分析师",
                    "round": 1,
                    "content": "第一轮看跌",
                },
            ],
        }
    )

    llm = FakeLLM("持有")
    result = create_research_manager(llm, FakeMemory())(state)

    prompt = llm.prompts[0]
    assert "最高优先级：核心数据表和原始报告中的可验证数据" in prompt
    assert "完整结构化辩论记录" in prompt
    assert "第1轮 - 看涨分析师：第一轮看涨" in prompt
    assert "第1轮 - 看跌分析师：第一轮看跌" in prompt
    assert result["investment_debate_state"]["latest_speaker"] == "manager"
    assert result["investment_debate_state"]["debate_turns"] == state["investment_debate_state"]["debate_turns"]


def test_analyze_request_rejects_invalid_debate_rounds():
    with pytest.raises(ValueError):
        AnalyzeRequest(ticker="600000.SH", max_debate_rounds=0)

    with pytest.raises(ValueError):
        AnalyzeRequest(ticker="600000.SH", max_risk_discuss_rounds=6)
