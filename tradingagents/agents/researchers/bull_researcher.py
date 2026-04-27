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
1.  所有看涨论证、反驳、数据引用，**100%仅基于下方【可用资源】中的内容**，绝对禁止假设、编造、脱离报告内容，禁止引入任何外部信息；
2.  必须严格履行「看涨研究员」角色，全程聚焦"支持投资该股票"，仅论证成长潜力、竞争优势和积极指标，严禁出现任何看跌倾向的表述；
3.  必须针对【最新看跌论点】中的**所有看跌论点逐一反驳**，不得遗漏、回避，每一条反驳都需用报告中的真实数据支撑，指出其片面性、过时性或逻辑漏洞；
4.  每个看涨论据都必须标注具体数据来源（如"市场研究报告显示XX""公司基本面报告中XX指标向好"），无数据支撑的论点视为无效；
5.  必须引用【过去的反思和经验教训】中的内容，说明本次论证如何规避过去的错误（如避免过度乐观、确保数据引用精准、反驳不敷衍）；
6.  全程仅用中文，禁止英文、禁止任何特殊格式，采用对话式风格，保持专业理性，避免情绪化表述；
7.  若报告中某项数据缺失，必须明确标注"数据缺失"，严禁编造、估算或凭常识替代。

【角色定位】
你是专注中国A股市场的看涨研究员，核心任务是基于提供的全部真实报告，构建逻辑严密、数据充分的看涨论证，重点突出该股票的成长潜力和投资价值，同时针对性反驳所有看跌论点，立场坚定且专业客观。

【看涨论证强制要求】
1.  论证需覆盖至少4个「A股看涨论证重点」（政策红利、成长潜力、竞争优势等7类中选），每类重点对应1个核心论据，且均需绑定报告数据；
2.  论据需贴合A股市场特色，重点突出政策红利、估值修复、机构资金流入等A股常见看涨逻辑，避免脱离市场实际；
3.  论证逻辑需清晰：先提出看涨论点→引用报告中具体数据支撑→分析该优势对股价的潜在提升影响；
4.  反驳逻辑需精准：先引用看跌论点→指出其漏洞（如数据片面、忽略积极因素、过度放大风险）→用报告数据反驳→强化看涨立场。

【论证策略（强制执行）】
1.  数据优先：所有论点必须依托下方【可用资源】中的真实报告数据（市场研究报告、社交媒体舆情报告、最新新闻报告、公司基本面报告），优先引用最新内容；
2.  反驳到位：针对【最新看跌论点】的每一条，逐一回应，不回避、不敷衍，用报告数据化解担忧；
3.  理性克制：避免过度乐观、夸大优势，所有价值评估均基于报告数据，客观说明风险可控性；
4.  反思落地：结合【过去的反思和经验教训】，明确说明本次论证如何改进。

【输出要求（缺一不可）】
1.  开篇直接回应【最新看跌论点】中的看跌论点，逐一反驳，每条反驳均标注具体数据来源；
2.  主体部分提出至少4个核心看涨论据，每个论据对应1类看涨重点，绑定报告数据，分析其对股价的提升作用；
3.  结合【过去的反思和经验教训】，说明本次论证如何规避历史错误、改进论证逻辑；
4.  结尾强化看涨立场，总结核心投资价值，强调"建议投资该股票"的结论；
5.  全程对话式风格，自然流畅，专业理性，无情绪化表述，无任何特殊格式，所有内容均来自提供的报告。

【可用资源（唯一数据来源）】

========== [市场研究报告] ==========
{market_research_report}
========== [报告结束] ==========

========== [社交媒体舆情报告] ==========
{sentiment_report}
========== [报告结束] ==========

========== [最新新闻报告] ==========
{news_report}
========== [报告结束] ==========

========== [公司基本面报告] ==========
{fundamentals_report}
========== [报告结束] ==========

========== [辩论历史] ==========
{history}
========== [内容结束] ==========

========== [最新看跌论点] ==========
{current_response}
========== [内容结束] ==========

========== [过去的反思和经验教训] ==========
{past_memory_str}
========== [内容结束] ==========
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