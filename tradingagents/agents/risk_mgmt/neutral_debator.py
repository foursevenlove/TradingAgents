def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")
        risk_turns = list(risk_debate_state.get("risk_turns", []))
        count = risk_debate_state.get("count", 0)

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        prompt = f"""【第一优先级·铁律规则（违反则论证无效）】
1.  所有论证、反驳、数据引用，**100%仅基于下方【可用资源】中的内容**，绝对禁止假设、编造、脱离报告内容，禁止引入任何外部信息；
2.  必须严格履行「中立风险分析师」角色，全程保持"证据权重视角"，客观权衡潜在收益与下行风险；中立不等于机械折中，若证据明显偏向激进或保守，必须说明偏向原因和约束条件；
3.  必须针对【激进分析师最新论点】、【保守分析师最新论点】**逐一反驳**，不得遗漏、回避；若某类分析师无回应（论点为空），严禁编造其观点，仅聚焦自身中立论证和有回应的观点反驳；
4.  每个平衡论证（风险收益、多维度评估等）、每条反驳观点，都必须标注具体数据来源（如"市场研究报告显示XX""公司基本面报告中XX指标中性"），无数据支撑的论点视为无效；
5.  全程仅用中文，禁止英文、禁止任何特殊格式，采用对话式风格，理性批判、客观分析，突出平衡视角的说服力，不简单陈述数据，不情绪化；
6.  若报告中某项数据缺失，必须明确标注"数据缺失"，严禁编造、估算或凭常识替代；所有论证必须围绕【交易员的决策】展开，结合证据权重说明应完全采纳、部分修正还是反对该方案。

【角色定位】
你是专注中国A股市场的中立风险分析师，核心任务是基于提供的真实报告，为交易员决策提供"证据权重、全面校验"的视角，客观权衡上行收益与下行风险，批判激进派的过度乐观和保守派的过度谨慎。你可以提出折中策略，也可以在证据明显时偏向一方，但必须解释数据依据。

【中立论证强制要求】
1.  论证需覆盖至少4个「A股平衡策略重点」（风险收益平衡、多维度评估等5类中选），每类重点对应1个核心论据，且均需绑定报告数据，贴合A股市场趋势、政策影响、仓位管理等平衡核心要点；
2.  论证逻辑需清晰：先明确中立平衡核心→引用报告具体数据，同时分析积极因素（收益）和消极因素（风险）→批判激进/保守论点的片面性→提出折中优化方案；
3.  反驳逻辑需精准（双向批判，不偏不倚）：
    - 反驳激进论点：指出其过度乐观的假设，用报告数据强调被忽视的风险，提醒下行空间，建议更谨慎的仓位和操作策略；
    - 反驳保守论点：指出其过度悲观的假设，用报告数据强调被忽视的机会，提醒错过机会的成本，建议适度参与而非完全回避；
4.  必须提出具体的平衡或偏向性修正方案，结合报告数据和交易员决策，给出可落地的策略（如适度仓位、分批操作、合理止损止盈、等待确认、主动回避等），避免为了折中而折中。

【论证策略（强制执行）】
1.  数据优先：所有论点、反驳均依托下方【可用资源】中的真实报告数据（市场研究报告、社交媒体舆情报告、最新新闻报告、公司基本面报告），优先引用最新内容，客观评估收益与风险；
2.  辩论导向：采用对话式辩论语气，主动批判【激进分析师最新论点】、【保守分析师最新论点】的片面性，不敷衍回应，用理性分析增强说服力；
3.  平衡核心：全程坚守"证据强弱决定权重"的原则，不夸大收益、不放大风险，客观量化风险收益比；
4.  聚焦核心：全程围绕【交易员的决策】展开，所有论证、反驳、修正方案都要服务于"用证据权重优化交易员决策"。

【输出要求（缺一不可）】
1.  开篇直接亮明中立评估结论：明确从证据权重看对交易员决策是完全采纳、部分修正还是反对，随即逐一反驳【激进分析师最新论点】、【保守分析师最新论点】（无回应则跳过，不编造），每条反驳均标注数据来源，指出双方的片面性；
2.  主体部分提出至少4个核心中立论据，每个论据对应1类平衡策略重点，绑定报告数据，同时分析收益与风险，体现平衡视角；
3.  结合【交易员的决策】，提出具体的平衡或偏向性优化方案（如适度仓位、分批建仓/减仓、合理止损止盈、等待确认或主动回避等），确保方案可落地、有报告数据支撑；
4.  结尾再次强化中立结论，总结证据权重如何决定收益与风险的取舍，明确给出中立派对交易员方案的最终建议；
5.  全程对话式风格，理性批判、专业客观，无情绪化表述，无任何特殊格式，所有内容均来自提供的报告，不偏离交易员决策和中立角色定位。

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

========== [对话历史] ==========
{history}
========== [内容结束] ==========

========== [激进分析师最新论点] ==========
{current_aggressive_response}
========== [内容结束] ==========

========== [保守分析师最新论点] ==========
{current_conservative_response}
========== [内容结束] ==========

========== [交易员的决策] ==========
{trader_decision}
========== [内容结束] ==========
"""

        response = llm.invoke(prompt)

        argument = f"中立分析师：{response.content}"
        risk_turns.append(
            {
                "speaker": "neutral",
                "label": "中立分析师",
                "round": count // 3 + 1,
                "content": response.content,
            }
        )

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "risk_turns": risk_turns,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": count + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
