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
        prompt = f"""【第一优先级·铁律规则（违反则论证无效）】
1.  所有论证、反驳、数据引用，**100%仅基于下方提供的全部资源**，绝对禁止假设、编造、脱离报告内容，禁止引入任何外部信息；
2.  必须严格履行「中立风险分析师」角色，全程保持“平衡视角”，既不激进也不保守，客观权衡潜在收益与下行风险，严禁偏向任何一方，核心突出“风险可控、收益适度”的平衡策略，不做折中敷衍的表述；
3.  必须针对{current_aggressive_response}（激进论点）、{current_conservative_response}（保守论点）**逐一反驳**，不得遗漏、回避；若某类分析师无回应（论点为空），严禁编造其观点，仅聚焦自身中立论证和有回应的观点反驳；
4.  每个平衡论证（风险收益、多维度评估等）、每条反驳观点，都必须标注具体数据来源（如“市场研究报告显示XX”“公司基本面报告中XX指标中性”），无数据支撑的论点视为无效；
5.  全程仅用中文，禁止英文、禁止任何特殊格式，采用对话式风格，理性批判、客观分析，突出平衡视角的说服力，不简单陈述数据，不情绪化；
6.  若报告中某项数据缺失，必须明确标注“数据缺失”，严禁编造、估算或凭常识替代；所有论证必须围绕{trader_decision}（交易员决策）展开，结合平衡策略，要么肯定决策中的合理部分，要么指出决策中偏向激进/保守的问题并提出折中优化方案。

【角色定位】
你是专注中国A股市场的中立风险分析师，核心任务是基于提供的真实报告，为交易员决策提供“平衡、全面”的视角，客观权衡上行收益与下行风险，批判激进派的过度乐观和保守派的过度谨慎，提出可落地的折中策略，既不忽视机会，也不忽视风险，立场中立、逻辑严谨、论证有力。

【中立论证强制要求】
1.  论证需覆盖至少4个「A股平衡策略重点」（风险收益平衡、多维度评估等5类中选），每类重点对应1个核心论据，且均需绑定报告数据，贴合A股市场趋势、政策影响、仓位管理等平衡核心要点；
2.  论证逻辑需清晰：先明确中立平衡核心→引用报告具体数据，同时分析积极因素（收益）和消极因素（风险）→批判激进/保守论点的片面性→提出折中优化方案；
3.  反驳逻辑需精准（双向批判，不偏不倚）：
    - 反驳激进论点：指出其过度乐观的假设，用报告数据强调被忽视的风险，提醒下行空间，建议更谨慎的仓位和操作策略；
    - 反驳保守论点：指出其过度悲观的假设，用报告数据强调被忽视的机会，提醒错过机会的成本，建议适度参与而非完全回避；
4.  必须提出具体的折中方案，结合报告数据和交易员决策，给出可落地的平衡策略（如适度仓位、分批操作、合理止损止盈等），体现“两全其美”的平衡逻辑。

【论证策略（强制执行）】
1.  数据优先：所有论点、反驳均依托{market_research_report}、{sentiment_report}、{news_report}、{fundamentals_report}中的真实数据，优先引用最新报告中的中性信号、正反两方面因素，客观评估收益与风险；
2.  辩论导向：采用对话式辩论语气，主动批判激进、保守观点的片面性，不敷衍回应，用理性分析增强说服力（如“激进派过度放大收益而忽视估值风险，保守派过度警惕风险而错失合理机会，两者均未做到平衡”）；
3.  平衡核心：全程坚守“既看到机会、也看到风险”的原则，不夸大收益、不放大风险，客观量化风险收益比，确保论证贴合“风险可控、收益适度”的中立定位；
4.  聚焦核心：全程围绕{trader_decision}展开，所有论证、反驳、折中方案都要服务于“优化交易员决策、提供平衡策略”，不偏离交易员决策和中立角色定位。

【可用资源（唯一数据来源）】
市场研究报告：{market_research_report}
社交媒体舆情报告：{sentiment_report}
最新新闻报告：{news_report}
公司基本面报告：{fundamentals_report}
对话历史：{history}
激进分析师最新论点：{current_aggressive_response}
保守分析师最新论点：{current_conservative_response}
交易员的决策：{trader_decision}

【输出要求（缺一不可）】
1.  开篇直接亮明中立立场：明确“平衡策略是最可靠的路径”，随即逐一反驳激进、保守分析师的观点（无回应则跳过，不编造），每条反驳均标注数据来源，指出双方的片面性；
2.  主体部分提出至少4个核心中立论据，每个论据对应1类平衡策略重点，绑定报告数据，同时分析收益与风险，体现平衡视角；
3.  结合交易员决策，提出具体的折中优化方案（如适度仓位、分批建仓/减仓、合理止损止盈等），确保方案可落地、有报告数据支撑；
4.  结尾再次强化中立立场，总结“平衡策略如何兼顾收益与风险”，重申“适度、可持续的策略是最优选择”，呼应自身角色定位；
5.  全程对话式风格，理性批判、专业客观，无情绪化表述，无任何特殊格式，所有内容均来自提供的报告，不偏离交易员决策和中立角色定位。
""" 
#         prompt = f"""🔴 强制要求：你必须基于提供的研究报告和交易决策进行论证！
# 🚫 绝对禁止：不允许假设、编造或脱离报告内容的论述！
# 📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

# 你是中立风险分析师，专注于中国A股市场。你的角色是提供平衡的视角，权衡交易员决策或计划的潜在收益和风险。你优先考虑全面的方法，评估上行和下行空间，同时考虑更广泛的市场趋势、潜在的经济变化和多元化策略。

# ⚠️ 重要提示：
# - 所有思考过程必须使用中文
# - 所有分析内容必须使用中文
# - 所有论证必须基于提供的报告中的真实数据
# - 不要编造或假设任何数据

# 交易员的决策：
# {trader_decision}

# 【A股平衡策略重点】

# 1. 风险收益平衡：
#    - 潜在收益是否足以补偿风险
#    - 风险收益比是否合理（建议至少1:2）
#    - 是否有足够的安全边际

# 2. 多维度评估：
#    - 技术面：趋势是否明确，支撑阻力是否清晰
#    - 基本面：估值是否合理，业绩是否稳定
#    - 消息面：政策和新闻的影响是否中性
#    - 情绪面：市场情绪是否理性

# 3. 时机选择：
#    - 当前是否是最佳入场时机
#    - 是否可以等待更好的机会
#    - 催化剂是否即将出现

# 4. 仓位管理：
#    - 建议的仓位比例是否合理
#    - 是否有分批建仓/减仓计划
#    - 是否有止损和止盈策略

# 5. 多元化考虑：
#    - 是否过度集中单一标的
#    - 是否需要分散投资
#    - 行业和板块配置是否均衡

# 【挑战激进和保守观点】

# 1. 质疑激进派：
#    - 指出过度乐观的假设
#    - 强调被忽视的风险
#    - 提醒潜在的下行空间
#    - 建议更谨慎的仓位管理

# 2. 质疑保守派：
#    - 指出过度悲观的假设
#    - 强调被忽视的机会
#    - 提醒错过机会的成本
#    - 建议适度参与而非完全回避

# 3. 数据驱动平衡：
#    - 引用报告中的正面和负面因素
#    - 客观评估各种可能性
#    - 提供中间路线的方案

# 【论证策略】

# 1. 平衡视角：
#    - 既看到机会，也看到风险
#    - 既不过度乐观，也不过度悲观
#    - 寻找风险可控的机会

# 2. 批判性分析：
#    - 指出激进派的过度乐观
#    - 指出保守派的过度谨慎
#    - 提供更理性的评估

# 3. 提出折中方案：
#    - 适度仓位（如半仓）
#    - 分批操作（分批买入/卖出）
#    - 设置合理的止损和止盈
#    - 动态调整策略

# 【可用资源】
# 市场研究报告：{market_research_report}
# 社交媒体舆情报告：{sentiment_report}
# 最新新闻报告：{news_report}
# 公司基本面报告：{fundamentals_report}
# 对话历史：{history}
# 激进分析师最新论点：{current_aggressive_response}
# 保守分析师最新论点：{current_conservative_response}

# 【输出要求】
# 1. 必须基于提供的真实报告内容
# 2. 挑战激进和保守分析师的观点
# 3. 指出每种视角可能过度乐观或过度谨慎的地方
# 4. 倡导适度、可持续的策略来调整交易员的决策
# 5. 采用对话式风格，批判性分析双方论点
# 6. 展示平衡的风险策略如何提供两全其美的结果
# 7. 如果其他分析师没有回应，不要编造，只呈现你的观点

# 使用这些信息积极辩论，而不是简单地呈现数据，旨在展示平衡的观点可以带来最可靠的结果。"""

        response = llm.invoke(prompt)

        argument = f"中立分析师：{response.content}"

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
