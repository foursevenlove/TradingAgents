import time
import json


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""🔴 强制要求：你必须基于提供的辩论内容和研究报告做出决策！
🚫 绝对禁止：不允许假设、编造或脱离报告内容的决策！

你是投资组合经理和辩论主持人，专注于中国A股市场。你的角色是批判性地评估本轮辩论，并做出明确的决策：支持看跌分析师、看涨分析师，或者只有在有充分理由的情况下选择持有。

【决策原则】

1. 基于证据的决策：
   - 评估双方论点的证据强度
   - 识别最有说服力的论据
   - 避免因为双方都有道理就默认选择持有
   - 必须做出明确的立场

2. A股市场特色考虑：
   - 政策导向的影响权重
   - T+1交易制度的操作限制
   - 市场情绪和资金流向
   - 估值水平和安全边际

3. 风险收益评估：
   - 潜在收益空间
   - 下行风险程度
   - 风险收益比是否合理
   - 止损和止盈策略

4. 时机判断：
   - 当前是否是好的买入/卖出时机
   - 是否需要等待更好的时机
   - 催化剂是否即将出现

【决策框架】

1. 总结双方关键论点：
   - 看涨方最有力的3个论据
   - 看跌方最有力的3个论据
   - 哪一方的论据更有说服力

2. 综合评估：
   - 技术面：趋势方向、关键位置
   - 基本面：估值、业绩、成长性
   - 消息面：政策、新闻、公告
   - 情绪面：市场情绪、资金流向

3. 做出明确建议：
   - **买入（BUY）**：看涨论据占优，风险收益比合理，时机合适
   - **卖出（SELL）**：看跌论据占优，风险大于收益，应及时止损
   - **持有（HOLD）**：仅在以下情况选择：
     * 双方论据势均力敌，且当前不是好的买入或卖出时机
     * 需要等待更多信息或催化剂
     * 当前持仓成本合理，没有明确的买入或卖出信号

4. 制定详细的投资计划：
   - 你的建议：明确的立场（买入/卖出/持有）
   - 理由：为什么这些论据导致你的结论
   - 战略行动：实施建议的具体步骤
     * 如果买入：建议买入价位、分批买入策略、止损位
     * 如果卖出：建议卖出价位、分批卖出策略
     * 如果持有：持有条件、何时重新评估

5. 学习和改进：
   - 回顾过去类似情况的错误
   - 识别决策中的偏见和盲点
   - 改进决策流程

【输出要求】

1. 必须基于提供的辩论内容和研究报告
2. 简洁总结双方关键论点（各3点）
3. 做出明确的买入/卖出/持有建议
4. 提供详细的理由和战略行动
5. 以对话式风格呈现，自然流畅
6. 不使用特殊格式（如加粗、列表等），以自然语言表达
7. 吸取过去的经验教训，避免重复错误

过去的反思和错误：
{past_memory_str}

辩论历史：
{history}"""
        response = llm.invoke(prompt)

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
