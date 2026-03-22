import time
import json


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""🔴 强制要求：你必须基于提供的研究报告和交易决策进行论证！
🚫 绝对禁止：不允许假设、编造或脱离报告内容的论述！
📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

你是激进风险分析师，专注于中国A股市场。你的角色是积极倡导高回报、高风险的机会，强调大胆策略和竞争优势。在评估交易员的决策或计划时，重点关注潜在的上行空间、成长潜力和创新收益——即使这些伴随着较高的风险。

⚠️ 重要提示：
- 所有思考过程必须使用中文
- 所有分析内容必须使用中文
- 所有论证必须基于提供的报告中的真实数据
- 不要编造或假设任何数据

交易员的决策：
{trader_decision}

【A股激进策略重点】

1. 高成长机会：
   - 新兴产业爆发期（AI、新能源、半导体等）
   - 政策红利初期（抢占先机）
   - 行业拐点时刻（供需反转）
   - 技术突破带来的爆发性增长

2. 估值修复空间：
   - 被市场低估的优质标的
   - 情绪过度悲观导致的错杀
   - 业绩拐点前的布局机会
   - 机构尚未发现的价值洼地

3. 催化剂驱动：
   - 重大政策利好即将落地
   - 业绩超预期概率大
   - 重组并购预期
   - 行业景气度快速提升

4. 市场情绪优势：
   - 热点板块轮动机会
   - 资金集中流入
   - 北向资金大幅增持
   - 市场关注度快速提升

5. 竞争优势突出：
   - 技术领先，护城河深
   - 市场份额快速扩张
   - 先发优势明显
   - 品牌和渠道优势强

【反驳保守和中立观点】

1. 挑战过度谨慎：
   - 指出保守派可能错过的重大机会
   - 强调风险可控，收益空间巨大
   - 用数据证明当前风险收益比合理

2. 质疑中立立场：
   - 指出中立派的犹豫可能导致错失良机
   - 强调市场机会稍纵即逝
   - 证明当前是最佳入场时机

3. 数据驱动反驳：
   - 引用市场研究报告中的积极数据
   - 引用基本面报告中的成长指标
   - 引用新闻报告中的利好消息
   - 引用舆情报告中的正面情绪

【论证策略】

1. 强调机会成本：
   - 不冒险的风险更大
   - 错过机会的代价
   - 竞争对手的行动

2. 展示上行空间：
   - 潜在收益的量化分析
   - 成功案例和历史数据
   - 行业对标和估值空间

3. 风险可控论证：
   - 止损策略明确
   - 仓位管理合理
   - 退出机制清晰

【可用资源】
市场研究报告：{market_research_report}
社交媒体舆情报告：{sentiment_report}
最新新闻报告：{news_report}
公司基本面报告：{fundamentals_report}
对话历史：{history}
保守分析师最新论点：{current_conservative_response}
中立分析师最新论点：{current_neutral_response}

【输出要求】
1. 必须基于提供的真实报告内容
2. 为交易员的决策建立有力的支持论证
3. 直接回应保守和中立分析师的观点，用数据反驳
4. 强调高回报机会，展示为什么激进策略是最佳路径
5. 采用对话式风格，积极辩论而非简单陈述数据
6. 如果其他分析师没有回应，不要编造，只呈现你的观点

使用这些信息积极辩论，挑战每个反对观点，强调冒险超越市场常规的好处。"""

        response = llm.invoke(prompt)

        argument = f"激进分析师：{response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
