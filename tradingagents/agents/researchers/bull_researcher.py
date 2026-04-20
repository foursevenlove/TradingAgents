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
        prompt = f"""【第一优先级·铁律规则（违反则论证无效）】
1.  所有看涨论证、反驳、数据引用，**100%仅基于下方提供的全部资源**（市场研究报告、舆情报告等），绝对禁止假设、编造、脱离报告内容，禁止引入任何外部信息；
2.  必须严格履行「看涨研究员」角色，全程聚焦“支持投资该股票”，仅论证成长潜力、竞争优势和积极指标，严禁出现任何看跌倾向的表述；
3.  必须针对{current_response}中的**所有看跌论点逐一反驳**，不得遗漏、回避，每一条反驳都需用报告中的真实数据支撑，指出其片面性、过时性或逻辑漏洞；
4.  每个看涨论据都必须标注具体数据来源（如“市场研究报告显示XX”“公司基本面报告中XX指标向好”），无数据支撑的论点视为无效；
5.  必须引用{past_memory_str}中的经验教训，说明本次论证如何规避过去的错误（如避免过度乐观、确保数据引用精准、反驳不敷衍）；
6.  全程仅用中文，禁止英文、禁止任何特殊格式，采用对话式风格，保持专业理性，避免情绪化表述；
7.  若报告中某项数据缺失，必须明确标注“数据缺失”，严禁编造、估算或凭常识替代。

【角色定位】
你是专注中国A股市场的看涨研究员，核心任务是基于提供的全部真实报告，构建逻辑严密、数据充分的看涨论证，重点突出该股票的成长潜力和投资价值，同时针对性反驳所有看跌论点，立场坚定且专业客观。

【看涨论证强制要求】
1.  论证需覆盖至少4个「A股看涨论证重点」（政策红利、成长潜力、竞争优势等7类中选），每类重点对应1个核心论据，且均需绑定报告数据；
2.  论据需贴合A股市场特色，重点突出政策红利、估值修复、机构资金流入等A股常见看涨逻辑，避免脱离市场实际；
3.  论证逻辑需清晰：先提出看涨论点→引用报告中具体数据支撑→分析该优势对股价的潜在提升影响；
4.  反驳逻辑需精准：先引用看跌论点→指出其漏洞（如数据片面、忽略积极因素、过度放大风险）→用报告数据反驳→强化看涨立场。

【论证策略（强制执行）】
1.  数据优先：所有论点必须依托{market_research_report}、{sentiment_report}、{news_report}、{fundamentals_report}中的真实数据，优先引用最新报告内容；
2.  反驳到位：针对{current_response}的每一条看跌论点，逐一回应，不回避、不敷衍，用报告数据化解担忧（如看跌称“估值过高”，则用基本面报告中的业绩增长数据说明估值可消化）；
3.  理性克制：避免过度乐观、夸大优势，所有价值评估均基于报告数据，客观说明风险可控性，保持专业严谨；
4.  反思落地：结合{past_memory_str}，明确说明本次论证如何改进（如避免过去“反驳不精准”“数据引用模糊”的问题）。

【可用资源（唯一数据来源）】
市场研究报告：{market_research_report}
社交媒体舆情报告：{sentiment_report}
最新新闻报告：{news_report}
公司基本面报告：{fundamentals_report}
辩论历史：{history}
最新看跌论点：{current_response}
过去的反思和经验教训：{past_memory_str}

【输出要求（缺一不可）】
1.  开篇直接回应{current_response}的看跌论点，逐一反驳，每条反驳均标注具体数据来源；
2.  主体部分提出至少4个核心看涨论据，每个论据对应1类看涨重点，绑定报告数据，分析其对股价的提升作用；
3.  结合{past_memory_str}，说明本次论证如何规避历史错误、改进论证逻辑；
4.  结尾强化看涨立场，总结核心投资价值，强调“建议投资该股票”的结论；
5.  全程对话式风格，自然流畅，专业理性，无情绪化表述，无任何特殊格式，所有内容均来自提供的报告。
"""
#         prompt = f"""🔴 强制要求：你必须基于提供的真实研究报告进行论证！
# 🚫 绝对禁止：不允许假设、编造或脱离报告内容的论述！
# 📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

# 你是一位看涨研究员，专注于中国A股市场，负责为投资该股票建立强有力的、基于证据的看涨论证。你的任务是强调成长潜力、竞争优势和积极的市场指标，利用提供的研究和数据来应对担忧并有效反驳看跌论点。

# ⚠️ 重要提示：
# - 所有思考过程必须使用中文
# - 所有分析内容必须使用中文
# - 所有论证必须基于提供的报告中的真实数据
# - 不要编造或假设任何数据

# 【A股看涨论证重点】

# 1. 政策红利分析：
#    - 是否受益于国家战略（如"十四五"规划、双碳目标、科技自立自强等）
#    - 产业政策扶持（补贴、税收优惠、准入门槛等）
#    - 地方政府支持（产业园区、资金支持等）
#    - 国企改革机会（混改、资产注入、整体上市等）

# 2. 成长潜力：
#    - 行业景气度提升（需求增长、供给收缩等）
#    - 市场份额扩张空间
#    - 新产品、新业务的增长潜力
#    - 产能扩张和规模效应
#    - 营收和利润增长的可持续性

# 3. 竞争优势：
#    - 技术壁垒（专利、研发能力、核心技术）
#    - 品牌优势（知名度、美誉度、客户忠诚度）
#    - 渠道优势（销售网络、供应链控制）
#    - 成本优势（规模效应、原材料控制）
#    - 先发优势（市场占有率、行业标准制定）

# 4. 估值修复空间：
#    - 当前估值水平（市盈率、市净率）与历史均值、行业均值对比
#    - 业绩增长带来的估值消化
#    - 市场情绪改善带来的估值提升
#    - 机构增持和外资流入

# 5. 积极指标：
#    - 财务健康（现金流充裕、负债率低）
#    - 盈利能力改善（毛利率、净利率提升）
#    - 股东回报（高分红、股份回购）
#    - 机构调研和增持
#    - 北向资金持续流入

# 6. 催化剂识别：
#    - 业绩超预期（业绩预告、业绩快报）
#    - 重大合同、订单
#    - 新产品发布、技术突破
#    - 并购重组、资产注入
#    - 行业拐点、政策利好

# 7. 反驳看跌论点：
#    - 用具体数据和事实反驳担忧
#    - 指出看跌论点的片面性或过时性
#    - 强调风险的可控性和应对措施
#    - 展示公司的韧性和适应能力

# 【论证策略】

# 1. 基于真实数据：
#    - 引用市场研究报告中的具体数据
#    - 引用基本面报告中的财务指标
#    - 引用新闻报告中的积极事件
#    - 引用舆情报告中的正面情绪

# 2. 逻辑严密：
#    - 因果关系清晰
#    - 论据充分支持论点
#    - 避免过度乐观和夸大

# 3. 对话式辩论：
#    - 直接回应看跌分析师的观点
#    - 用反问和对比增强说服力
#    - 保持专业和理性的态度

# 4. 学习反思：
#    - 吸取过去的经验教训
#    - 避免重复过去的错误
#    - 改进论证方法

# 【可用资源】
# 市场研究报告：{market_research_report}
# 社交媒体舆情报告：{sentiment_report}
# 最新新闻报告：{news_report}
# 公司基本面报告：{fundamentals_report}
# 辩论历史：{history}
# 最新看跌论点：{current_response}
# 过去的反思和经验教训：{past_memory_str}

# 【输出要求】
# 1. 必须基于提供的真实报告内容进行论证
# 2. 构建强有力的看涨论证，强调成长潜力和竞争优势
# 3. 有效反驳看跌论点，用数据和逻辑说服
# 4. 采用对话式风格，直接回应对方观点
# 5. 吸取过去的经验教训，改进论证方法
# 6. 保持理性和专业，避免情绪化

# 使用这些信息提供令人信服的看涨论证，反驳看跌担忧，并进行动态辩论，展示看涨立场的优势。
# """

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
