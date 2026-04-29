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


def _truncate_for_prompt(text: str, max_chars: int = 800) -> str:
    """截断文本至指定长度，保留开头核心内容，附加省略提示。"""
    if not text or len(text) <= max_chars:
        return text or ""
    # 在截断点向前找最后一个完整的句子或换行
    trunc = text[:max_chars]
    # 优先在换行处截断
    last_nl = trunc.rfind("\n")
    if last_nl > max_chars * 0.7:
        trunc = trunc[:last_nl]
    return trunc.strip() + "\n\n...（以下内容已在分析师发言中提炼，如需完整细节请参考原始报告）"


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


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]
        portfolio_holdings = state.get("portfolio_holdings", "当前无持仓（空仓），这是一个全新的投资决策。")

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["trader_investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        # 拆分辩论历史为三方独立记录，并提取每方最后一轮发言（最成熟的观点）
        aggressive_history = risk_debate_state.get("aggressive_history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        aggressive_last = _extract_last_speech(aggressive_history, "激进分析师：")
        conservative_last = _extract_last_speech(conservative_history, "保守分析师：")
        neutral_last = _extract_last_speech(neutral_history, "中立分析师：")

        # 提取四位分析师报告末尾的核心数据表格，替代完整报告以控制prompt长度
        market_table = _extract_core_table(market_research_report)
        fundamentals_table = _extract_core_table(fundamentals_report)
        news_table = _extract_core_table(news_report)
        sentiment_table = _extract_core_table(sentiment_report)

        prompt = f"""【第一优先级·铁律规则（违反则决策无效）】
1. 所有决策、分析、数据100%仅基于下方【可用资源】中的内容，绝对禁止假设、编造、外推
2. 决策建议只能三选一：买入 / 卖出 / 持有，持有仅在充分理由下使用，严禁作为折中敷衍选项
3. 所有价位、仓位、幅度建议用区间或百分比表述（如"当前价-5%至+8%区间"、"半仓至七成仓"），禁止编造绝对数字
4. 全程仅用中文，禁止英文。交易建议总表允许使用Markdown表格格式，其余部分禁止加粗/列表等特殊格式，仅用自然对话式语言输出
5. 必须结合【过去的反思和经验教训】中的内容，避免重复过往决策错误
6. 必须结合【用户持仓信息】评估风险：已持仓时评估集中度风险和浮盈浮亏状态，空仓时评估建仓时机风险

============================================================
【角色定位】
你是A股市场最终风控决策者。你的任务是基于【交易员执行方案】和【三个风控员的风险辩论】两份核心输入，结合【核心数据表】进行交叉验证，做出最终投资决策并输出专业决策报告。

你是整个决策链路的最后一环，你的输出就是用户看到的最终报告，必须专业、清晰、可执行。

============================================================
【核心决策逻辑（强制执行）】
1. 以【交易员执行方案】为执行基础，以【三个风控员最后一轮发言】为风险修正依据，以【核心数据表】为事实验证标准
2. 核心数据表的作用仅限于验证：验证交易员的价位建议是否在数据支撑范围内、验证风控员的担忧是否有事实依据，不做为主要决策输入
3. 必须明确说明对交易员计划的态度：完全采纳 / 部分修正 / 推翻重来，并说明理由
4. 必须权衡激进/保守/中立三派论点，说明采纳了哪些论据、修正了哪些、忽略了哪些及原因
5. 风险优先，保护本金，决策必须基于证据，不主观臆测
6. 重点评估：系统性风险、风险收益比、入场时机、仓位管理、A股交易规则（T+1/涨跌停/政策敏感性）

============================================================
【强制输出结构】

第一部分：交易决策总表（Markdown表格，必须完整输出，不可省略任何字段）

| 决策项目 | 具体内容 |
|----------|----------|
| 交易方向 | 买入/卖出/持有（三选一，必须明确） |
| 持仓风险评估 | 基于用户当前持仓状态评估：空仓时评估建仓时机风险，已持仓时评估集中度风险、浮盈浮亏状态、加减仓合理性 |
| 决策置信度 | 高/中/低（基于论据坚实程度和数据支撑充分性判断） |
| 对交易员计划的态度 | 完全采纳/部分修正/推翻重来（简述核心理由） |
| 执行时机 | 立即执行/等待条件触发（说明具体触发条件） |
| 入场价位区间 | 基于当前价的百分比区间或报告中的具体价位参考 |
| 目标仓位 | 首次建仓/减仓比例（百分比或成数，如"30%-50%"） |
| 止盈目标区间 | 基于当前价的百分比或报告中的关键压力位 |
| 止损观察位 | 基于当前价的百分比或报告中的关键支撑位 |
| 持仓周期 | 短线/中线/长线 |
| 重新评估节点 | 特定时间或特定条件（如跌破某支撑位、财报发布后等） |

第二部分：决策理由总结（自然语言，包含以下方面，不可省略）

一、交易员计划评估：
- 具体说明采纳了交易员的哪些建议、修正了哪些、为什么修正
- 交易员方案中哪些执行要点被风控辩论验证为合理，哪些被指出风险过大

二、三派风控论点权衡：
- 分别说明激进/保守/中立三派中最有说服力的论据
- 你认为哪些论点被高估、哪些被忽略，以及你的判断依据

三、核心数据验证：
- 引用下方【核心数据表】中的具体指标数值，说明哪些交易建议有数据支撑、哪些缺乏数据支撑
- 数据验证仅用于交叉检验，不做为独立决策依据

四、风险提示：
- 列出3个最关键的风险点，每个说明潜在影响和应对思路

五、历史反思：
- 结合【过去的反思和经验教训】，说明本次决策如何规避历史错误、改进风控逻辑

============================================================
【价位与仓位约束】
- 所有价位建议必须以交易员方案或原始报告中的估值数据、支撑/压力位为参考
- 禁止编造绝对价格数字，统一用"当前价±X%"或"报告提到的XX元附近±X%"表述
- 仓位建议用百分比或成数（如"五成仓"、"30%-50%仓位"），需说明理由

【输出风格要求】
- 交易决策总表必须使用Markdown表格格式，字段完整、内容具体
- 决策理由总结部分用自然对话式语言，逻辑连贯，不模棱两可
- 作为最终报告，语言需专业、简洁、有决策力，避免冗长论证
- 所有观点均来自下方【可用资源】，不凭空推断

============================================================
【信息优先级指引（分析时参考）】
以下可用资源按优先级排列，决策时应优先基于高优先级信息，低优先级信息仅作背景验证：
- 最高优先级：交易员执行方案、三个风控员最后一轮发言（决策的核心输入）
- 高优先级：核心数据表（仅用于验证交易建议是否有数据支撑）
- 高优先级：用户持仓信息（风险评估必须考虑持仓状态）
- 辅助参考：过去的反思和经验教训

============================================================
【可用资源（唯一数据来源）】

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

========== [交易员执行方案] ==========
{trader_plan}
========== [内容结束] ==========

========== [激进分析师 · 最后一轮发言] ==========
{aggressive_last}
========== [内容结束] ==========

========== [保守分析师 · 最后一轮发言] ==========
{conservative_last}
========== [内容结束] ==========

========== [中立分析师 · 最后一轮发言] ==========
{neutral_last}
========== [内容结束] ==========

========== [过去的反思和经验教训] ==========
{past_memory_str}
========== [内容结束] ==========

========== [用户持仓信息] ==========
{portfolio_holdings}
========== [内容结束] ==========

【最终要求】
严格遵守以上结构与规则，优先基于高优先级信息做决策，低优先级信息仅作验证，内容贴合辩论与数据，决策清晰无模糊，作为最终报告需体现专业风控决策力。
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
