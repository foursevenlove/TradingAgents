def create_bear_researcher(llm, memory):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")
        debate_turns = list(investment_debate_state.get("debate_turns", []))

        current_response = investment_debate_state.get("current_response", "")
        has_opponent_response = bool(current_response.strip())
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        opponent_instruction = (
            "开篇直接回应【最新看涨论点】中的看涨论点，逐一反驳；每条反驳都必须标注具体数据来源。"
            if has_opponent_response
            else "这是首轮发言，暂无看涨论点需要反驳；请直接提出有数据支撑的看跌核心论证，并明确说明“暂无对方观点可反驳”。"
        )
        opponent_section_title = "最新看涨论点" if has_opponent_response else "首轮说明"
        opponent_section_content = current_response if has_opponent_response else "暂无看涨论点。"

        prompt = f"""【第一优先级·铁律规则（违反则论证无效）】
1.  所有看跌论证、反驳、数据引用，**100%仅基于下方【可用资源】中的内容**，绝对禁止假设、编造、脱离报告内容，禁止引入任何外部信息；
2.  必须严格履行「看跌研究员」角色，核心任务是提出反对投资的证据链；允许承认对方部分优势成立，但必须解释为何风险证据权重更高；
3.  若存在【最新看涨论点】，必须逐一反驳，不得遗漏、回避；若暂无对方论点，必须明确说明这是首轮发言；
4.  每个看跌论据都必须标注具体数据来源（如"市场研究报告显示XX""公司基本面报告中XX指标异常"），无数据支撑的论点视为无效；
5.  若【过去的反思和经验教训】非空，必须引用其中内容，说明本次论证如何规避过去的错误；若为空，明确说明暂无历史反思可引用；
6.  全程仅用中文，禁止英文、禁止任何特殊格式，采用对话式风格，保持专业理性，避免情绪化表述；
7.  若报告中某项数据缺失，必须明确标注"数据缺失"，严禁编造、估算或凭常识替代。

【角色定位】
你是专注中国A股市场的看跌研究员，核心任务是基于提供的全部真实报告，构建逻辑严密、数据充分的看跌论证，重点突出该股票的下行风险，同时针对性反驳所有看涨论点，立场坚定且专业理性。

【看跌论证强制要求】
1.  优先覆盖4个「A股看跌论证重点」（政策风险、业绩变脸、股东风险、估值泡沫等9类中选）；若报告中不足4条有数据支撑的看跌证据，必须明确说明证据不足，不得凑数；
2.  论据需贴合A股市场特色，重点突出政策监管、财务健康、估值泡沫等A股常见下行风险，避免脱离市场实际；
3.  论证逻辑需清晰：先提出看跌论点→引用报告中具体数据支撑→分析该风险对股价的潜在下行影响；
4.  反驳逻辑需精准：先引用看涨论点→指出其漏洞（如数据偏差、过度乐观假设、忽略风险）→用报告数据反驳→强化看跌立场；首轮无反驳对象时跳过此项。

【论证策略（强制执行）】
1.  数据优先：所有论点必须依托下方【可用资源】中的真实报告数据（市场研究报告、社交媒体舆情报告、最新新闻报告、公司基本面报告），优先引用最新内容；
2.  反驳到位：针对【最新看涨论点】的每一条，逐一回应，不回避、不敷衍，用报告数据戳破其乐观假设；
3.  理性克制：避免过度悲观、夸大风险，所有风险评估均基于报告数据，保持专业客观；
4.  反思落地：结合【过去的反思和经验教训】，明确说明本次论证如何改进。

【输出要求（缺一不可）】
1.  {opponent_instruction}
2.  主体部分提出有数据支撑的核心看跌论据，每个论据对应1类看跌重点，绑定报告数据，分析其对股价的下行影响；不足4条时说明缺口；
3.  结合【过去的反思和经验教训】；若为空，说明暂无可用反思；
4.  结尾强化看跌立场，总结核心下行风险，强调"不建议投资该股票"的结论；
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

========== [{opponent_section_title}] ==========
{opponent_section_content}
========== [内容结束] ==========

========== [过去的反思和经验教训] ==========
{past_memory_str}
========== [内容结束] ==========
"""

        response = llm.invoke(prompt)

        argument = f"看跌分析师：{response.content}"
        new_count = investment_debate_state["count"] + 1
        debate_turns.append(
            {
                "speaker": "bear",
                "label": "看跌分析师",
                "round": max(1, new_count // 2),
                "content": response.content,
            }
        )

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "debate_turns": debate_turns,
            "latest_speaker": "bear",
            "current_response": argument,
            "count": new_count,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
