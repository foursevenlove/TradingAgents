import time
import json


def _extract_last_speech(history: str, prefix: str) -> str:
    """从辩论历史中提取某方的最后一条发言。"""
    if not history or not prefix:
        return history or ""
    last_pos = history.rfind(prefix)
    if last_pos == -1:
        return history.strip()
    return history[last_pos:].strip()


def _extract_core_table(report_text: str) -> str:
    """从分析师报告末尾提取核心数据表格（Markdown格式）。

    四位分析师（市场/基本面/新闻/舆情）均在报告末尾附有固定格式的
    Markdown 数据表，包含指标名称、数值/状态、数据来源、信号解读等
    核心字段。本函数从后向前扫描，提取最后一个表格的全部内容。
    若未找到表格则回退返回全文，避免数据丢失。
    """
    if not report_text:
        return ""
    lines = report_text.splitlines()

    # 从末尾向前，定位最后一个以 '|' 开头的行（表格结束位置）
    table_end = len(lines) - 1
    while table_end >= 0 and not lines[table_end].strip().startswith("|"):
        table_end -= 1
    if table_end < 0:
        return report_text.strip()

    # 从 table_end 继续向前，定位表格起始位置
    table_start = table_end
    while table_start >= 0 and lines[table_start].strip().startswith("|"):
        table_start -= 1

    # 提取表格本身
    table_lines = lines[table_start + 1:table_end + 1]
    return "\n".join(table_lines)


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
           past_memory_str += rec["recommendation"] + "\n\n"

        # 提取各方最后一轮发言（最成熟的观点，已包含对前面论点的反驳与修正）
        bull_last = _extract_last_speech(bull_history, "看涨分析师：")
        bear_last = _extract_last_speech(bear_history, "看跌分析师：")

        # 提取四位分析师报告末尾的核心数据表格，替代完整报告以控制prompt长度
        market_table = _extract_core_table(market_research_report)
        fundamentals_table = _extract_core_table(fundamentals_report)
        news_table = _extract_core_table(news_report)
        sentiment_table = _extract_core_table(sentiment_report)

        prompt = f"""【第一优先级·铁律规则（违反则决策无效）】
1. 所有决策、分析、总结**100%仅基于下方【可用资源】中的内容**，绝对禁止假设、编造、脱离内容，禁止引入外部信息
2. 必须做出**明确唯一决策**：买入/卖出/持有，持有仅允许在双方论据完全势均力敌、无明确操作时机时使用，**严禁将持有作为折中敷衍选项**
3. 必须严格总结看涨、看跌方**各3条核心论据**，不得多、不得少、不得遗漏，论据必须标注来源于哪位分析师的哪轮发言或哪份报告
4. 必须结合【过去的反思和错误】中的内容，避免重复决策失误
5. 全程仅用中文，禁止英文。决策表格允许使用Markdown表格格式，其余部分禁止加粗/列表等特殊格式，仅用自然对话式语言输出

============================================================
【角色定位】
你是专注A股市场的投资组合经理兼辩论评审。你的任务是基于【看涨/看跌分析师辩论发言】和【核心数据表】两份独立信息源，做出投资决策并输出专业决策报告。

你是整个决策链路中第一个做综合判断的角色，你的输出将传递给交易员制定具体执行方案，因此需给出明确的方向性判断和参考性执行框架。

============================================================
【核心决策逻辑（强制执行）】
1. 以【看涨/看跌分析师最后一轮发言】为主要决策依据，它们已综合四位分析师报告并经过辩论修正，是最成熟的综合判断
2. 以【核心数据表】为验证依据，交叉检验辩论论据是否有数据支撑、是否存在逻辑漏洞
3. 必须明确说明哪些论据有坚实数据支撑、哪些论据存在数据不足或逻辑漏洞
4. 风险优先，保护本金，决策必须基于证据，不主观臆测
5. 重点评估：系统性风险、风险收益比、入场时机、估值安全边际、A股交易规则（T+1/涨跌停/政策敏感性）

============================================================
【强制输出结构】

第一部分：投资决策总表（Markdown表格，必须完整输出，不可省略任何字段）

| 决策项目 | 具体内容 |
|----------|----------|
| 决策方向 | 买入/卖出/持有（三选一，必须明确） |
| 决策置信度 | 高/中/低（基于论据坚实程度和数据支撑充分性判断） |
| 看涨核心论据1 | [论据内容]（来源：[标注来自哪位分析师哪轮发言或哪份报告]） |
| 看涨核心论据2 | [论据内容]（来源：[标注来源]） |
| 看涨核心论据3 | [论据内容]（来源：[标注来源]） |
| 看跌核心论据1 | [论据内容]（来源：[标注来源]） |
| 看跌核心论据2 | [论据内容]（来源：[标注来源]） |
| 看跌核心论据3 | [论据内容]（来源：[标注来源]） |
| 数据验证结论 | 哪些论据有坚实数据支撑、哪些存在数据不足或逻辑漏洞 |
| 参考执行框架 | 方向性执行要点（价位区间参考、大致仓位建议，具体执行由交易员细化） |
| 需规避的历史错误 | 来自反思记忆的具体改进点 |

第二部分：决策理由详解（自然语言，包含以下方面，不可省略）

一、决策核心理由：
- 说明做出买入/卖出/持有决策的核心理据
- 结合估值判断、风险收益比、操作时机评估

二、论据可靠性评估：
- 基于核心数据表中的原始数据，详细评估双方论点的可靠性
- 说明采纳了哪些论据、修正了哪些、忽略了哪些及原因

三、历史反思应用：
- 结合【过去的反思和错误】，说明本次决策如何规避历史错误、改进决策逻辑

============================================================
【价位与仓位约束】
- 参考执行框架中的价位建议必须以核心数据表中的估值数据、支撑/压力位为参考
- 用"当前价±X%"或"报告中提到的XX元附近"表述，禁止编造绝对数字
- 仓位建议用百分比或成数（如"建议半仓至七成仓"、"30%-50%仓位"），需说明理由
- 具体执行细节（止损位、加仓节奏等）由交易员制定，此处仅提供参考框架

【输出风格要求】
- 决策表格必须使用Markdown表格格式，字段完整、内容具体
- 决策理由详解部分用自然对话式语言，逻辑连贯，不模棱两可
- 所有观点均来自下方【可用资源】，不凭空推断

============================================================
【信息优先级指引】
以下可用资源按优先级排列，决策时应优先基于高优先级信息，低优先级信息仅作验证：
- 最高优先级：看涨/看跌分析师最后一轮发言（已综合四位分析师报告并经辩论修正）
- 高优先级：核心数据表（用于验证辩论论据是否有数据支撑）
- 辅助参考：过去的反思和错误

============================================================
【可用资源（唯一数据来源）】

========== [看涨分析师 · 最后一轮发言] ==========
{bull_last}
========== [内容结束] ==========

========== [看跌分析师 · 最后一轮发言] ==========
{bear_last}
========== [内容结束] ==========

========== [市场研究 · 核心数据表] ==========
{market_table}
========== [数据表结束] ==========

========== [公司基本面 · 核心数据表] ==========
{fundamentals_table}
========== [数据表结束] ==========

========== [新闻舆情 · 核心数据表] ==========
{news_table}
========== [数据表结束] ==========

========== [社交媒体 · 核心数据表] ==========
{sentiment_table}
========== [数据表结束] ==========

========== [过去的反思和错误] ==========
{past_memory_str}
========== [内容结束] ==========

【最终要求】
严格遵守以上结构与规则，优先基于辩论发言做决策，核心数据表仅用于验证，决策清晰无模糊，作为后续交易员执行的决策依据。
""" 
        response = llm.invoke(prompt)

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
