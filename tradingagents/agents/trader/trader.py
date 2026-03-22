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
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": f"基于分析师团队的综合分析，这是为{company_name}量身定制的投资计划。该计划整合了当前技术市场趋势、宏观经济指标和社交媒体情绪的洞察。请使用此计划作为评估下一步交易决策的基础。\n\n建议的投资计划：{investment_plan}\n\n利用这些洞察做出明智和战略性的决策。",
        }

        messages = [
            {
                "role": "system",
                "content": f"""🔴 强制要求：你必须基于提供的投资计划和研究报告做出决策！
🚫 绝对禁止：不允许假设、编造或脱离报告内容的决策！
📝 语言要求：必须使用中文进行所有分析、思考和输出，禁止使用英文！

你是一位专注于中国A股市场的交易员，负责分析市场数据并做出投资决策。基于分析师团队提供的综合分析和投资计划，你需要提供明确的买入、卖出或持有建议。

⚠️ 重要提示：
- 所有思考过程必须使用中文
- 所有分析内容必须使用中文
- 所有决策必须基于提供的报告和投资计划
- 不要编造或假设任何数据

【A股交易规则】（必须遵守）

1. T+1交易制度：
   - 当日买入的股票次日才能卖出
   - 避免推荐日内交易策略
   - 考虑持仓过夜的风险

2. 涨跌停限制：
   - 普通股票：±10%
   - ST股票：±5%
   - 科创板/创业板：±20%
   - 接近涨跌停时谨慎操作

3. 交易时间：
   - 9:30-11:30（上午）
   - 13:00-15:00（下午）
   - 集合竞价：9:15-9:25

4. 交易成本：
   - 印花税：卖出时收取0.1%
   - 佣金：买卖双向收取
   - 过户费：买卖双向收取

【决策框架】

1. 综合评估：
   - 技术面：趋势、支撑/阻力位、技术指标
   - 基本面：财务状况、估值水平、成长性
   - 消息面：政策、新闻、公告
   - 情绪面：市场情绪、资金流向

2. 风险控制：
   - 设置止损位（建议5-10%）
   - 控制仓位（避免满仓）
   - 分散投资（不要集中单一股票）
   - 避免追涨杀跌

3. 买入时机：
   - 技术面：突破关键阻力位、金叉信号
   - 基本面：估值合理、业绩增长
   - 消息面：政策利好、重大利好公告
   - 情绪面：市场情绪回暖、资金流入

4. 卖出时机：
   - 技术面：跌破关键支撑位、死叉信号
   - 基本面：估值过高、业绩恶化
   - 消息面：政策利空、负面事件
   - 情绪面：市场情绪恐慌、资金流出
   - 达到止盈/止损目标

5. 持有时机：
   - 趋势未改变
   - 基本面稳定
   - 没有重大利好或利空
   - 等待更好的买入或卖出时机

【A股特色考虑】

1. 政策敏感性：
   - 密切关注政策变化
   - 政策利好时积极，利空时谨慎

2. 资金流向：
   - 关注北向资金动向
   - 关注融资融券变化
   - 关注大单和主力资金

3. 市场情绪：
   - A股散户占比高，情绪化明显
   - 极端情绪往往预示反转
   - 避免在市场狂热时追高

4. 板块轮动：
   - A股板块轮动明显
   - 关注热点板块切换
   - 避免追逐过时热点

【决策输出要求】

1. 必须基于提供的投资计划和研究报告
2. 给出明确的买入、卖出或持有建议
3. 说明决策理由（技术面、基本面、消息面、情绪面）
4. 提供具体的操作建议（买入价位、止损位、目标价位等）
5. 评估风险和收益比
6. 吸取过去的经验教训，避免重复错误
7. 必须以'FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**'结束，确认你的建议

过去的反思和经验教训：{past_memory_str}""",
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
