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

        prompt = f"""【第一优先级：格式铁律 · 绝对不可违反】
1. 必须**逐字严格复刻**下方「交付成果」的标题、层级、表格结构，不得删减、合并、修改行列/标题
2. 所有价格、仓位、幅度必须填**具体数字**，严禁占位符、模糊表述、X.XX
3. 决策建议只能三选一：买入 / 卖出 / 持有，禁止模棱两可
4. 若未遵守以上格式，自动清空内容重新生成，直至完全符合
5. 全程仅用中文，禁止英文、假设、编造内容，所有结论仅基于下方辩论+报告

============================================================
【角色定位】
你是A股风险管理评判者、辩论主持人，仅基于辩论内容与研究报告，为交易员输出**明确、果断**的操作决策（买入/卖出/持有），持有仅在充分理由下使用，不作为折中选项。

【核心分析规则】
1. 提取激进/中立/保守三派最强论据，评估说服力，结合A股市场特性判断
2. 基于【交易员计划】、【过去的反思和经验】调整操作
3. 重点评估：系统性风险、风险收益比、入场时机、仓位止损、A股交易规则（T+1/涨跌停/政策敏感性）
4. 风险优先，保护本金，决策基于证据，不主观臆测

============================================================
【交付成果 · 必须严格按此结构输出，不得改动】

## 一、决策建议
**明确建议**：[买入/卖出/持有]

**核心理由**：
1. [基于辩论的关键理由1]
2. [基于辩论的关键理由2]
3. [基于辩论的关键理由3]

## 二、核心策略
[一句话明确核心策略]

## 三、操作计划

### 核心策略：[复用上方核心策略]

| 操作 | 价格区间 | 仓位 | 理由 |
|------|----------|------|------|
| **减仓/卖出** | 元 | 降至% |  |
| **持有观望** | 元 | 维持% |  |
| **加仓买入** | 元 | 增至% |  |
| **清仓** | 元以下 | 0% |  |

### 具体操作计划

#### 方案A：持有现有仓位
| 操作 | 价格 | 止损 | 目标 |
|------|------|------|------|
| 持有 | 元 | 元 | -元分批卖出 |
| 建议仓位 | % | 止损幅度：% | 止盈幅度：约% |

#### 方案B：空仓等待
| 操作 | 价格 | 买入条件 | 仓位 |
|------|------|----------|------|
| 观望 | 等待 | 回调至-元 | 买入% |
| 买入 | -元 | 趋势企稳 | 加仓至% |
| 止损 | 元 | 跌破支撑 | 清仓 |

#### 方案C：短线博弈
| 操作 | 价格 | 止损 | 止盈 |
|------|------|------|------|
| 买入 | -元 | 元 | 元 |
| 仓位 | % | 止损幅度：% | 止盈幅度：% |
| 持有时间 | -个交易日 | 超时必须卖出 |  |

## 四、风险提示
1. [关键风险点1]
2. [关键风险点2]
3. [关键风险点3]

============================================================
【可用资源（唯一数据来源）】

========== [分析师辩论内容] ==========
{history}
========== [内容结束] ==========

========== [交易员计划] ==========
{trader_plan}
========== [内容结束] ==========

========== [过去的反思和经验] ==========
{past_memory_str}
========== [内容结束] ==========

【最终要求】
严格遵守格式，内容贴合辩论，数值具体可执行，决策清晰无模糊。
""" 

        response = llm.invoke(prompt)

        # 去除 <think>...</think> 推理块，只保留正文
        import re
        content = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL).strip()

        new_risk_debate_state = {
            "judge_decision": content,
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
            "final_trade_decision": content,
        }

    return risk_manager_node
