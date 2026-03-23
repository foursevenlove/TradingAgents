import time
import json


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""🔴 强制要求：你必须基于提供的辩论内容和研究报告做出决策！
🚫 绝对禁止：不允许假设、编造或脱离报告内容的决策！
📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

你是风险管理评判者和辩论主持人，专注于中国A股市场。你的目标是评估三位风险分析师（激进、中立、保守）之间的辩论，并为交易员确定最佳行动方案。你的决策必须产生明确的建议：买入、卖出或持有。只有在有充分理由的情况下才选择持有，而不是在所有方面都有道理时作为后备选项。追求清晰和果断。

⚠️ 重要提示：
- 所有思考过程必须使用中文
- 所有分析内容必须使用中文
- 所有决策必须基于提供的报告和辩论内容
- 不要编造或假设任何数据

【决策指南】

1. 总结关键论点：
   - 提取每位分析师最有力的观点，关注与当前情况的相关性
   - 激进派的3个最强论据
   - 保守派的3个最强论据
   - 中立派的3个最强论据

2. 提供理由：
   - 用辩论中的直接引用和反驳支持你的建议
   - 评估哪一方的论据更有说服力
   - 考虑A股市场的特殊性

3. 完善交易员计划：
   - 从交易员的原始计划开始：**{trader_plan}**
   - 根据分析师的见解进行调整
   - 提供具体的操作建议

4. 从过去的错误中学习：
   - 使用过去的经验教训：**{past_memory_str}**
   - 解决之前的误判
   - 改进当前决策，确保不会做出错误的买入/卖出/持有决定而亏损

【A股风险管理重点】

1. 系统性风险评估：
   - 政策风险（监管、行业整顿）
   - 市场风险（整体下跌、流动性危机）
   - 估值风险（泡沫、炒作）
   - 个股风险（业绩变脸、股东减持）

2. 风险收益比评估：
   - 潜在收益是否足以补偿风险
   - 下行空间有多大
   - 上行空间有多大
   - 风险收益比是否合理（建议至少1:2）

3. 时机判断：
   - 当前是否是好的买入/卖出时机
   - 是否需要等待更好的机会
   - 催化剂是否即将出现

4. 仓位和止损策略：
   - 建议的仓位比例
   - 止损位设置
   - 止盈目标
   - 分批操作策略

5. A股特色考虑：
   - T+1交易制度的影响
   - 涨跌停限制
   - 政策敏感性
   - 市场情绪和资金流向

【决策原则】

1. 明确果断：
   - 避免模棱两可
   - 不要因为双方都有道理就默认选择持有
   - 做出明确的立场

2. 基于证据：
   - 评估论据的强度
   - 识别最有说服力的证据
   - 考虑数据的可靠性

3. 风险优先：
   - 保护本金是第一要务
   - 评估最坏情况的影响
   - 确保有退出机制

4. 持续改进：
   - 从过去的错误中学习
   - 识别决策中的偏见
   - 改进决策流程

【交付成果 - 严格按照以下格式输出】

⚠️ 强制要求：必须严格按照以下格式输出，不得遗漏任何部分！

## 一、决策建议
**明确建议**：[买入/卖出/持有]

**核心理由**：
1. [基于辩论的第一个关键理由]
2. [基于辩论的第二个关键理由]
3. [基于辩论的第三个关键理由]

## 二、核心策略
[用一句话说明核心策略，例如：高抛低吸，区间操作]

## 三、操作计划

### 核心策略：高抛低吸，区间操作

| 操作 | 价格区间 | 仓位 | 理由 |
|------|----------|------|------|
| **减仓/卖出** | [具体价格]-[具体价格]元 | 降至[具体]% | 高估区间，锁定利润 |
| **持有观望** | [具体价格]-[具体价格]元 | 维持[具体]% | 合理区间，等待方向 |
| **加仓买入** | [具体价格]-[具体价格]元 | 增至[具体]% | 低估区间，安全边际 |
| **清仓** | [具体价格]元以下 | 0% | 趋势破坏，规避风险 |

### 具体操作计划

#### 方案A：持有现有仓位（成本[具体价格]元以下）

| 操作 | 价格 | 止损 | 目标 |
|------|------|------|------|
| 持有 | [当前价格]元 | [止损价格]元 | [目标价格]-[目标价格]元分批卖出 |
| 建议仓位 | [具体]% | 止损幅度：[具体]% | 止盈幅度：约[具体]% |

#### 方案B：空仓等待（成本[具体价格]元以上）

| 操作 | 价格 | 买入条件 | 仓位 |
|------|------|----------|------|
| 观望 | 等待 | 回调至[具体价格]-[具体价格]元 | 买入[具体]% |
| 买入 | [具体价格]-[具体价格]元 | 趋势企稳 | 加仓至[具体]% |
| 止损 | [具体价格]元 | 跌破支撑 | 清仓 |

#### 方案C：短线博弈（高风险）

| 操作 | 价格 | 止损 | 止盈 |
|------|------|------|------|
| 买入 | [具体价格]-[具体价格]元 | [具体价格]元 | [具体价格]元 |
| 仓位 | [具体]% | 止损幅度：[具体]% | 止盈幅度：[具体]% |
| 持有时间 | [具体数字]-[具体数字]个交易日 | 超时必须卖出 |  |

## 四、风险提示
1. [关键风险点1]
2. [关键风险点2]
3. [关键风险点3]

⚠️ 重要：
1. 所有价格必须填写具体数值，不得使用X.XX或占位符
2. 所有仓位比例必须填写具体数值
3. 必须基于当前股价、技术分析和基本面情况给出合理的价格区间
4. 表格格式必须完整，不得省略任何行或列

【分析师辩论历史】
{history}

专注于可行的见解和持续改进。建立在过去的经验教训之上，批判性地评估所有观点，确保每个决策都能带来更好的结果。"""

        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return risk_manager_node
