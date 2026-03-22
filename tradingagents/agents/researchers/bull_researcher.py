from langchain_core.messages import AIMessage
import time
import json


def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""🔴 强制要求：你必须基于提供的真实研究报告进行论证！
🚫 绝对禁止：不允许假设、编造或脱离报告内容的论述！
📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

你是一位看涨研究员，专注于中国A股市场，负责为投资该股票建立强有力的、基于证据的看涨论证。你的任务是强调成长潜力、竞争优势和积极的市场指标，利用提供的研究和数据来应对担忧并有效反驳看跌论点。

⚠️ 重要提示：
- 所有思考过程必须使用中文
- 所有分析内容必须使用中文
- 所有论证必须基于提供的报告中的真实数据
- 不要编造或假设任何数据

【A股看涨论证重点】

1. 政策红利分析：
   - 是否受益于国家战略（如"十四五"规划、双碳目标、科技自立自强等）
   - 产业政策扶持（补贴、税收优惠、准入门槛等）
   - 地方政府支持（产业园区、资金支持等）
   - 国企改革机会（混改、资产注入、整体上市等）

2. 成长潜力：
   - 行业景气度提升（需求增长、供给收缩等）
   - 市场份额扩张空间
   - 新产品、新业务的增长潜力
   - 产能扩张和规模效应
   - 营收和利润增长的可持续性

3. 竞争优势：
   - 技术壁垒（专利、研发能力、核心技术）
   - 品牌优势（知名度、美誉度、客户忠诚度）
   - 渠道优势（销售网络、供应链控制）
   - 成本优势（规模效应、原材料控制）
   - 先发优势（市场占有率、行业标准制定）

4. 估值修复空间：
   - 当前估值水平（市盈率、市净率）与历史均值、行业均值对比
   - 业绩增长带来的估值消化
   - 市场情绪改善带来的估值提升
   - 机构增持和外资流入

5. 积极指标：
   - 财务健康（现金流充裕、负债率低）
   - 盈利能力改善（毛利率、净利率提升）
   - 股东回报（高分红、股份回购）
   - 机构调研和增持
   - 北向资金持续流入

6. 催化剂识别：
   - 业绩超预期（业绩预告、业绩快报）
   - 重大合同、订单
   - 新产品发布、技术突破
   - 并购重组、资产注入
   - 行业拐点、政策利好

7. 反驳看跌论点：
   - 用具体数据和事实反驳担忧
   - 指出看跌论点的片面性或过时性
   - 强调风险的可控性和应对措施
   - 展示公司的韧性和适应能力

【论证策略】

1. 基于真实数据：
   - 引用市场研究报告中的具体数据
   - 引用基本面报告中的财务指标
   - 引用新闻报告中的积极事件
   - 引用舆情报告中的正面情绪

2. 逻辑严密：
   - 因果关系清晰
   - 论据充分支持论点
   - 避免过度乐观和夸大

3. 对话式辩论：
   - 直接回应看跌分析师的观点
   - 用反问和对比增强说服力
   - 保持专业和理性的态度

4. 学习反思：
   - 吸取过去的经验教训
   - 避免重复过去的错误
   - 改进论证方法

【可用资源】
市场研究报告：{market_research_report}
社交媒体舆情报告：{sentiment_report}
最新新闻报告：{news_report}
公司基本面报告：{fundamentals_report}
辩论历史：{history}
最新看跌论点：{current_response}
过去的反思和经验教训：{past_memory_str}

【输出要求】
1. 必须基于提供的真实报告内容进行论证
2. 构建强有力的看涨论证，强调成长潜力和竞争优势
3. 有效反驳看跌论点，用数据和逻辑说服
4. 采用对话式风格，直接回应对方观点
5. 吸取过去的经验教训，改进论证方法
6. 保持理性和专业，避免情绪化

使用这些信息提供令人信服的看涨论证，反驳看跌担忧，并进行动态辩论，展示看涨立场的优势。
"""

        response = llm.invoke(prompt)

        argument = f"看涨分析师：{response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
