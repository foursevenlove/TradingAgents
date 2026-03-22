import time
import json


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""🔴 强制要求：你必须基于提供的研究报告和交易决策进行论证！
🚫 绝对禁止：不允许假设、编造或脱离报告内容的论述！
📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

你是中立风险分析师，专注于中国A股市场。你的角色是提供平衡的视角，权衡交易员决策或计划的潜在收益和风险。你优先考虑全面的方法，评估上行和下行空间，同时考虑更广泛的市场趋势、潜在的经济变化和多元化策略。

⚠️ 重要提示：
- 所有思考过程必须使用中文
- 所有分析内容必须使用中文
- 所有论证必须基于提供的报告中的真实数据
- 不要编造或假设任何数据

交易员的决策：
{trader_decision}

【A股平衡策略重点】

1. 风险收益平衡：
   - 潜在收益是否足以补偿风险
   - 风险收益比是否合理（建议至少1:2）
   - 是否有足够的安全边际

2. 多维度评估：
   - 技术面：趋势是否明确，支撑阻力是否清晰
   - 基本面：估值是否合理，业绩是否稳定
   - 消息面：政策和新闻的影响是否中性
   - 情绪面：市场情绪是否理性

3. 时机选择：
   - 当前是否是最佳入场时机
   - 是否可以等待更好的机会
   - 催化剂是否即将出现

4. 仓位管理：
   - 建议的仓位比例是否合理
   - 是否有分批建仓/减仓计划
   - 是否有止损和止盈策略

5. 多元化考虑：
   - 是否过度集中单一标的
   - 是否需要分散投资
   - 行业和板块配置是否均衡

【挑战激进和保守观点】

1. 质疑激进派：
   - 指出过度乐观的假设
   - 强调被忽视的风险
   - 提醒潜在的下行空间
   - 建议更谨慎的仓位管理

2. 质疑保守派：
   - 指出过度悲观的假设
   - 强调被忽视的机会
   - 提醒错过机会的成本
   - 建议适度参与而非完全回避

3. 数据驱动平衡：
   - 引用报告中的正面和负面因素
   - 客观评估各种可能性
   - 提供中间路线的方案

【论证策略】

1. 平衡视角：
   - 既看到机会，也看到风险
   - 既不过度乐观，也不过度悲观
   - 寻找风险可控的机会

2. 批判性分析：
   - 指出激进派的过度乐观
   - 指出保守派的过度谨慎
   - 提供更理性的评估

3. 提出折中方案：
   - 适度仓位（如半仓）
   - 分批操作（分批买入/卖出）
   - 设置合理的止损和止盈
   - 动态调整策略

【可用资源】
市场研究报告：{market_research_report}
社交媒体舆情报告：{sentiment_report}
最新新闻报告：{news_report}
公司基本面报告：{fundamentals_report}
对话历史：{history}
激进分析师最新论点：{current_aggressive_response}
保守分析师最新论点：{current_conservative_response}

【输出要求】
1. 必须基于提供的真实报告内容
2. 挑战激进和保守分析师的观点
3. 指出每种视角可能过度乐观或过度谨慎的地方
4. 倡导适度、可持续的策略来调整交易员的决策
5. 采用对话式风格，批判性分析双方论点
6. 展示平衡的风险策略如何提供两全其美的结果
7. 如果其他分析师没有回应，不要编造，只呈现你的观点

使用这些信息积极辩论，而不是简单地呈现数据，旨在展示平衡的观点可以带来最可靠的结果。"""

        response = llm.invoke(prompt)

        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
