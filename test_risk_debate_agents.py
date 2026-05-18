from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.graph.propagation import Propagator
from tradingagents.recommendation.analysis_validator import normalize_graph_result


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
            "trader_investment_plan": "交易员建议卖出，等待更明确信号。",
        }
    )
    return state


def test_aggressive_debator_records_structured_turn_and_is_not_trader_advocate():
    llm = FakeLLM("激进视角认为仍需评估机会成本。")
    result = create_aggressive_debator(llm)(_base_state())

    prompt = llm.prompts[0]
    debate = result["risk_debate_state"]

    assert "你不是交易员的辩护人" in prompt
    assert "完全采纳、部分修正还是反对" in prompt
    assert debate["latest_speaker"] == "Aggressive"
    assert debate["count"] == 1
    assert debate["risk_turns"] == [
        {
            "speaker": "aggressive",
            "label": "激进分析师",
            "round": 1,
            "content": llm.content,
        }
    ]
    assert debate["current_aggressive_response"] == f"激进分析师：{llm.content}"


def test_risk_manager_uses_structured_debate_and_data_first_rules():
    state = _base_state()
    state["risk_debate_state"].update(
        {
            "aggressive_history": "\n激进分析师：第一轮激进",
            "conservative_history": "\n保守分析师：第一轮保守",
            "neutral_history": "\n中立分析师：第一轮中立",
            "history": "\n激进分析师：第一轮激进\n保守分析师：第一轮保守\n中立分析师：第一轮中立",
            "risk_turns": [
                {
                    "speaker": "aggressive",
                    "label": "激进分析师",
                    "round": 1,
                    "content": "第一轮激进",
                },
                {
                    "speaker": "conservative",
                    "label": "保守分析师",
                    "round": 1,
                    "content": "第一轮保守",
                },
                {
                    "speaker": "neutral",
                    "label": "中立分析师",
                    "round": 1,
                    "content": "第一轮中立",
                },
            ],
            "current_aggressive_response": "激进分析师：第一轮激进",
            "current_conservative_response": "保守分析师：第一轮保守",
            "current_neutral_response": "中立分析师：第一轮中立",
            "count": 3,
        }
    )

    llm = FakeLLM("最终风控结论")
    result = create_risk_manager(llm, FakeMemory())(state)

    prompt = llm.prompts[0]
    assert "最高优先级：核心数据表中的可验证数据" in prompt
    assert "完整结构化风控辩论记录" in prompt
    assert "第1轮 - 激进分析师：第一轮激进" in prompt
    assert "空仓时只能给出建仓或观望" in prompt
    assert "未找到历史反思记录" in prompt
    assert result["risk_debate_state"]["risk_turns"] == state["risk_debate_state"]["risk_turns"]
    assert result["final_trade_decision"] == "最终风控结论"


def test_validation_summary_uses_risk_judge_decision_from_state_dict():
    result = normalize_graph_result(
        {
            "risk_debate_state": {
                "judge_decision": "风控经理最终建议持有。",
                "history": "不应作为摘要优先项",
            }
        },
        "600000.SH",
    )

    assert result.risk_summary == "风控经理最终建议持有。"
