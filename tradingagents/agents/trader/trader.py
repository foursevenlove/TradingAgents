import functools
import time
import json


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "未找到历史记忆。"

        context = {
            "role": "user",
            "content": f"基于分析师团队的综合分析，这是为{company_name}量身定制的投资计划。该计划整合了当前技术市场趋势、宏观经济指标和社交媒体情绪的洞察。请使用此计划作为评估下一步交易决策的基础。\n\n建议的投资计划：{investment_plan}\n\n利用这些洞察做出明智和战略性的决策。",
        }
        prompt = f"""【第一优先级·铁律指令（违反则决策无效）】
1. 所有分析、决策、数据100%仅基于提供的投资计划与研究报告，绝对禁止假设、编造、外推、脱离内容
2. 必须严格遵守下方列明的A股全部交易规则，不得给出日内交易、违背涨跌停/T+1制度的建议
3. 必须给出明确唯一决策：买入 / 持有 / 卖出，严禁模棱两可
4. 全文仅使用中文，禁止任何英文（结尾固定句式除外）
5. 结尾必须严格输出：FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**，不得修改、删减、替换格式
6. 必须结合历史教训，避免重复过往决策错误

【角色】
你是专注A股市场的职业交易员，基于研究报告与投资计划，结合风控要求给出可执行、合规的交易决策。

【必须严格遵守的A股交易规则】
1. T+1制度：当日买入次日才可卖出，禁止日内交易策略，需考虑隔夜风险
2. 涨跌幅限制：普通股±10%、ST±5%、科创板/创业板±20%，涨跌停附近谨慎操作
3. 交易时间：9:30-11:30、13:00-15:00；集合竞价9:15-9:25
4. 交易成本：卖出印花税0.1%，买卖双向收取佣金与过户费

【强制分析框架（缺一不可）】
1. 综合判断：从技术面、基本面、消息面、情绪面四维度给出依据
2. 风险控制：明确止损位（5%-10%）、建议仓位、风控逻辑
3. 实操计划：具体价位区间、止盈目标、分批操作思路
4. 风险收益比：量化收益空间与下行风险
5. 历史反思：结合过往教训说明本次如何避坑

【输出要求】
1. 语言自然流畅，对话式表达，不使用特殊排版
2. 所有理由均来自报告内容，无外部信息
3. 操作建议具体可落地，不含模糊表述
4. 立场清晰，不摇摆、不折中
5. 结尾严格输出指定固定句式

【可用依据】
过去的反思和经验教训：{past_memory_str}

"""
        messages = [
            {
                "role": "system",
                "content": prompt,
            },
            context,
        ]

        result = llm.invoke(messages)

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
