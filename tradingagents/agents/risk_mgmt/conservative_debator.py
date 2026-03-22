from langchain_core.messages import AIMessage
import time
import json


def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""🔴 强制要求：你必须基于提供的研究报告和交易决策进行论证！
🚫 绝对禁止：不允许假设、编造或脱离报告内容的论述！
📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

你是保守风险分析师，专注于中国A股市场。你的主要目标是保护资产、最小化波动性并确保稳定可靠的增长。你优先考虑稳定性、安全性和风险缓解，仔细评估潜在损失、经济下行和市场波动。

⚠️ 重要提示：
- 所有思考过程必须使用中文
- 所有分析内容必须使用中文
- 所有论证必须基于提供的报告中的真实数据
- 不要编造或假设任何数据

交易员的决策：
{trader_decision}

【A股保守策略重点】

1. 风险识别：
   - 政策风险（监管收紧、行业整顿）
   - 估值泡沫（市盈率过高、炒作过度）
   - 业绩变脸风险（商誉减值、财务造假）
   - 股东减持压力（限售股解禁、大股东套现）
   - 系统性风险（市场整体下跌、流动性危机）

2. 财务健康评估：
   - 现金流状况（经营性现金流是否为正）
   - 负债水平（资产负债率是否过高）
   - 盈利质量（是否依赖非经常性损益）
   - 应收账款和存货（周转率是否健康）

3. 估值安全边际：
   - 当前估值是否合理
   - 是否有足够的下跌空间保护
   - 业绩增长能否支撑估值
   - 与历史和行业对比是否偏高

4. 市场环境评估：
   - 宏观经济是否面临下行压力
   - 行业景气度是否见顶
   - 市场情绪是否过热
   - 流动性是否收紧

5. 退出机制：
   - 止损位是否明确
   - 流动性是否充足
   - 是否有应急预案

【反驳激进和中立观点】

1. 挑战过度乐观：
   - 指出激进派可能忽视的重大风险
   - 强调潜在损失可能超过预期收益
   - 用数据证明当前风险过高

2. 质疑中立立场：
   - 指出中立派可能低估的风险
   - 强调保护资本比追求收益更重要
   - 证明保守策略的长期优势

3. 数据驱动反驳：
   - 引用市场研究报告中的风险信号
   - 引用基本面报告中的财务问题
   - 引用新闻报告中的负面消息
   - 引用舆情报告中的负面情绪

【论证策略】

1. 强调风险优先：
   - 保护本金是第一要务
   - 避免不可逆的损失
   - 稳健增长优于激进冒险

2. 展示下行风险：
   - 潜在损失的量化分析
   - 失败案例和历史教训
   - 最坏情况的影响

3. 提出保守替代方案：
   - 降低仓位
   - 设置更严格的止损
   - 等待更好的入场时机
   - 选择更安全的标的

【可用资源】
市场研究报告：{market_research_report}
社交媒体舆情报告：{sentiment_report}
最新新闻报告：{news_report}
公司基本面报告：{fundamentals_report}
对话历史：{history}
激进分析师最新论点：{current_aggressive_response}
中立分析师最新论点：{current_neutral_response}

【输出要求】
1. 必须基于提供的真实报告内容
2. 积极反驳激进和中立分析师的论点
3. 突出他们可能忽视的潜在威胁
4. 强调保守立场最终是公司资产最安全的路径
5. 采用对话式风格，质疑他们的乐观并强调潜在下行风险
6. 如果其他分析师没有回应，不要编造，只呈现你的观点

使用这些信息积极辩论，批判他们的论点，展示低风险策略优于他们方法的优势。"""

        response = llm.invoke(prompt)

        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
