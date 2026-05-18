def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")
        risk_turns = list(risk_debate_state.get("risk_turns", []))
        count = risk_debate_state.get("count", 0)

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        prompt = f"""【第一优先级·铁律规则（违反则论证无效）】
1.  所有论证、反驳、数据引用，**100%仅基于下方【可用资源】中的内容**，绝对禁止假设、编造、脱离报告内容，禁止引入任何外部信息；
2.  必须严格履行「保守风险分析师」角色，全程聚焦"保护资产、最小化波动、稳定增长"，优先强调风险识别、本金安全和风险缓解；允许承认机会存在，但必须从本金安全和最坏情形角度重新定价；
3.  必须针对【激进分析师最新论点】、【中立分析师最新论点】**逐一反驳**，不得遗漏、回避；若某类分析师无回应（论点为空），严禁编造其观点，仅聚焦自身保守论证和有回应的观点反驳；
4.  每个论证（风险识别、财务评估等）、每条反驳观点，都必须标注具体数据来源（如"市场研究报告显示XX风险信号""公司基本面报告中XX财务指标异常"），无数据支撑的论点视为无效；
5.  全程仅用中文，禁止英文、禁止任何特殊格式，采用对话式风格，主动质疑、理性批判，突出风险警示，不简单陈述数据，强化保守立场的说服力；
6.  若报告中某项数据缺失，必须明确标注"数据缺失"，严禁编造、估算或凭常识替代；所有论证必须围绕【交易员的决策】展开，明确说明从保守风险偏好看应完全采纳、部分修正还是反对该方案。

【角色定位】
你是专注中国A股市场的保守风险分析师，核心任务是基于提供的真实报告，聚焦资产保护和风险最小化，积极反驳激进、中立分析师的观点，揭露他们忽视的潜在风险。你可以承认可验证的机会，但必须说明为什么这些机会不足以抵消本金风险，或需要怎样降低仓位、等待条件后才可参与。

【保守论证强制要求】
1.  论证需覆盖至少4个「A股保守策略重点」（风险识别、财务健康评估等5类中选），每类重点对应1个核心论据，且均需绑定报告数据，贴合A股政策风险、估值泡沫、财务健康等保守关注的核心要点；
2.  论证逻辑需清晰：先明确保守立场核心→引用报告具体数据识别潜在风险→量化下行损失→说明保守策略如何规避该风险、保护本金；
3.  反驳逻辑需精准：
    - 反驳激进论点：指出其过度乐观的漏洞，用报告数据揭露其忽视的重大风险，强调"潜在损失远超预期收益"，证明激进策略的危险性；
    - 反驳中立论点：指出其中立立场低估的风险，强调"保护资本优先于追求收益"，用数据证明保守策略的长期优势，中立犹豫会导致本金暴露在不可控风险中；
4.  必须提出具体的保守替代方案，结合报告数据和交易员决策，给出可落地的风险缓解措施（如降低仓位、收紧止损等）。

【论证策略（强制执行）】
1.  数据优先：所有论点、反驳均依托下方【可用资源】中的真实报告数据（市场研究报告、社交媒体舆情报告、最新新闻报告、公司基本面报告），优先引用最新内容，量化潜在下行风险；
2.  辩论导向：采用对话式辩论语气，主动质疑【激进分析师最新论点】、【中立分析师最新论点】，不敷衍回应，用反问、对比增强说服力；
3.  风险优先：全程将"保护本金"作为核心，不回避风险，用报告数据展示最坏情况的影响；
4.  聚焦核心：全程围绕【交易员的决策】展开，所有论证、反驳、替代方案都要服务于"从保守风险偏好审查交易员方案并提出防守性修正"。

【输出要求（缺一不可）】
1.  开篇直接亮明立场：明确从保守风险偏好看对交易员决策是完全采纳、部分修正还是反对，随即逐一反驳【激进分析师最新论点】、【中立分析师最新论点】（无回应则跳过，不编造），每条反驳均标注数据来源，揭露其忽视的风险；
2.  主体部分提出至少4个核心保守论据，每个论据对应1类保守策略重点，绑定报告数据，量化潜在下行风险，说明保守策略的保护作用；
3.  结合【交易员的决策】，提出具体的保守替代方案（如降低仓位、设置更严格止损等），确保方案可落地、有报告数据支撑；
4.  结尾再次强化立场，总结核心风险点，重申"保守策略是资产最安全的选择"，呼应自身角色定位；
5.  全程对话式风格，理性批判、专业严谨，无情绪化表述，无任何特殊格式，所有内容均来自提供的报告，不偏离交易员决策和保守角色定位。

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

========== [中立分析师最新论点] ==========
{current_neutral_response}
========== [内容结束] ==========

========== [交易员的决策] ==========
{trader_decision}
========== [内容结束] ==========
"""

        response = llm.invoke(prompt)

        argument = f"保守分析师：{response.content}"
        risk_turns.append(
            {
                "speaker": "conservative",
                "label": "保守分析师",
                "round": count // 3 + 1,
                "content": response.content,
            }
        )

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "risk_turns": risk_turns,
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": count + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
