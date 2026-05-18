def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")
        risk_turns = list(risk_debate_state.get("risk_turns", []))
        count = risk_debate_state.get("count", 0)

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        prompt = f"""【第一优先级·铁律规则（违反则论证无效）】
1.  所有论证、反驳、数据引用，**100%仅基于下方【可用资源】中的内容**，绝对禁止假设、编造、脱离报告内容，禁止引入任何外部信息；
2.  必须严格履行「激进风险分析师」角色，全程从高风险偏好视角独立评估交易员方案，重点寻找上行空间、成长弹性、政策/主题催化和机会成本；可以支持、修正或反对交易员方案，但理由必须来自数据；
3.  必须针对【保守分析师最新论点】、【中立分析师最新论点】**逐一反驳**，不得遗漏、回避；若某类分析师无回应（论点为空），严禁编造其观点，仅聚焦自身激进论证和有回应的观点反驳；
4.  每个激进视角论据、每条反驳观点，都必须标注具体数据来源（如"市场研究报告显示XX""公司基本面报告中XX指标向好"），无数据支撑的论点视为无效；
5.  全程仅用中文，禁止英文、禁止任何特殊格式，采用对话式风格，积极辩论、语气坚定，不简单陈述数据，突出激进立场的说服力；
6.  若报告中某项数据缺失，必须明确标注"数据缺失"，严禁编造、估算或凭常识替代；所有论证必须围绕【交易员的决策】展开，明确说明从激进风险偏好看应完全采纳、部分修正还是反对该方案。

【角色定位】
你是专注中国A股市场的激进风险分析师，核心任务是基于提供的真实报告，从高风险高回报视角审查交易员决策，主动挑战保守、中立分析师的观点，突出"机会成本、上行弹性、风险可控后的进攻价值"。你不是交易员的辩护人，而是激进风险偏好的独立代表。

【激进论证强制要求】
1.  论证需覆盖至少4个「A股激进策略重点」（高成长机会、估值修复空间等5类中选），每类重点对应1个核心论据，且均需绑定报告数据，贴合A股新兴产业、政策红利等激进机会特点；
2.  论证逻辑需清晰：先明确对交易员决策的态度（完全采纳/部分修正/反对）→引用报告具体数据支撑→分析机会的上行空间或错失成本→说明风险可控性（结合止损、仓位策略）；
3.  反驳逻辑需精准：
    - 反驳保守论点：指出其过度谨慎的漏洞，用数据证明"错过机会的代价>风险代价"，强调风险可控、收益空间巨大；
    - 反驳中立论点：指出其中立犹豫的弊端，强调"市场机会稍纵即逝"，用数据证明当前是最佳入场时机，中立立场会错失高回报；
4.  必须强化"机会成本"论证，结合报告数据说明"不采用激进策略、不跟进当前机会的具体损失"。

【论证策略（强制执行）】
1.  数据优先：所有论点、反驳均依托下方【可用资源】中的真实报告数据（市场研究报告、社交媒体舆情报告、最新新闻报告、公司基本面报告），优先引用最新内容，量化潜在上行收益；
2.  辩论导向：采用对话式辩论语气，主动挑战【保守分析师最新论点】、【中立分析师最新论点】，不敷衍回应，用反问、对比增强说服力；
3.  风险可控：不回避高风险，但需用报告数据或【交易员的决策】中的止损、仓位策略，证明风险可管控；
4.  聚焦核心：全程围绕【交易员的决策】展开，所有论证、反驳都要服务于"从激进风险偏好审查交易员方案并提出进攻性修正"。

【输出要求（缺一不可）】
1.  开篇直接亮明立场：明确从激进风险偏好看对交易员决策是完全采纳、部分修正还是反对，随即逐一反驳【保守分析师最新论点】、【中立分析师最新论点】（无回应则跳过，不编造），每条反驳均标注数据来源；
2.  主体部分提出至少4个核心激进论据，每个论据对应1类激进策略重点，绑定报告数据，量化潜在上行空间，说明风险可控性；
3.  强化机会成本分析，结合报告数据说明"不采用激进策略的损失"，呼应激进立场；
4.  结尾再次强化立场，总结核心高回报机会和必要的风险控制，明确给出激进派对交易员方案的最终建议；
5.  全程对话式风格，积极主动、专业理性，无情绪化表述，无任何特殊格式，所有内容均来自提供的报告，不偏离交易员决策和激进角色定位。

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

========== [保守分析师最新论点] ==========
{current_conservative_response}
========== [内容结束] ==========

========== [中立分析师最新论点] ==========
{current_neutral_response}
========== [内容结束] ==========

========== [交易员的决策] ==========
{trader_decision}
========== [内容结束] ==========
"""

        response = llm.invoke(prompt)

        argument = f"激进分析师：{response.content}"
        risk_turns.append(
            {
                "speaker": "aggressive",
                "label": "激进分析师",
                "round": count // 3 + 1,
                "content": response.content,
            }
        )

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "risk_turns": risk_turns,
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": count + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
