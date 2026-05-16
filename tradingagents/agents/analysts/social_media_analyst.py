from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
from datetime import datetime, timedelta
import uuid

from tradingagents.agents.utils.agent_utils import get_social_sentiment


REQUIRED_SOCIAL_TOOLS = ("get_social_sentiment",)


def _get_social_date_range(trade_date: str) -> tuple[str, str]:
    end_day = datetime.strptime(str(trade_date)[:10], "%Y-%m-%d")
    start_day = end_day - timedelta(days=3)
    return start_day.strftime("%Y-%m-%d"), end_day.strftime("%Y-%m-%d")


def _executed_social_tools(messages) -> set[str]:
    tool_call_names = {}
    executed = set()

    for message in messages:
        for tool_call in getattr(message, "tool_calls", None) or []:
            name = tool_call.get("name")
            tool_id = tool_call.get("id")
            if name in REQUIRED_SOCIAL_TOOLS and tool_id:
                tool_call_names[tool_id] = name

        if type(message).__name__ == "ToolMessage":
            name = getattr(message, "name", None)
            if name in REQUIRED_SOCIAL_TOOLS:
                executed.add(name)
                continue

            tool_call_id = getattr(message, "tool_call_id", None)
            if tool_call_id in tool_call_names:
                executed.add(tool_call_names[tool_call_id])

    return executed


def _forced_social_tool_call(tool_name: str, ticker: str, start_date: str, end_date: str):
    return {
        "name": tool_name,
        "args": {
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
        },
        "id": f"call_{tool_name}_{uuid.uuid4().hex[:8]}",
    }


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        start_date, end_date = _get_social_date_range(current_date)

        tools = [
            get_social_sentiment,
        ]
        system_message = f"""
【第一优先级 · 铁律指令（违反则输出全部无效）】
1. 工具调用强制规则：
   - 输出前必须调用 `get_social_sentiment` 获取免费社交舆情代理指标，参数必须为：`ticker={ticker}`、`start_date={start_date}`、`end_date={end_date}`；
   - 未调用工具直接输出=无效答案，需重新执行调用；
   - 工具调用失败时，必须在报告开头明确说明：“工具调用失败：get_social_sentiment调用失败，原因：[标注失败原因]”，不得编造任何舆情内容；
2. 数据真实性铁律：
   - 所有热度、排名、参与意愿、关键词和情绪判断仅来自工具返回结果，严禁编造、假设、凭常识作答；
   - 信息缺失时必须标注“信息缺失”，禁止用猜测替代；
3. 免费数据边界：
   - 免费接口只提供东方财富/雪球公开热度代理指标和部分新闻情绪背景，不提供真实评论样本、发布者身份、KOL粉丝量、微博全文或精确评论情绪占比；
   - 严禁输出“正面评论占比/负面评论占比/中性评论占比”“雪球热帖数量”“微博讨论量”“KOL观点”等工具未返回的精确数据；
4. 语言要求：全程仅用中文，禁止任何英文内容。

【角色定位】
你是专注中国A股市场的社交热度代理分析师，基于免费公开接口返回的真实热度指标，评估市场关注度、讨论热度、参与意愿和事件情绪对股价的短期/长期影响，为后续决策提供舆情维度依据。

【核心分析规则】
1. 指标可得性优先：
   - 有排名/变化/参与意愿/关注指数/关键词时，必须引用具体工具返回值；
   - 没有具体数值时写“信息缺失”，不得补估值；
   - 若接口返回失败或无数据，应降低该维度可信度。
2. 平台边界：
   - 东方财富指标可用于衡量A股散户关注度和市场参与意愿；
   - 雪球关注榜/讨论榜只能作为全市场热度参照，若未直接命中目标股票，必须说明“仅作市场热度背景”；
   - 免费层暂不覆盖微博、知乎、同花顺社区原文评论。
3. 影响评估：
   - 区分“关注度升高带来的短期波动风险”和“基本面趋势”，社交热度不得直接等同于买卖建议；
   - 明确短期影响、长期影响和可信度，避免把热度代理指标过度解读为真实情绪比例。

【输出要求（必须严格遵守结构，缺一不可）】
1. 报告整体结构：
   - 开头：标注“数据来源：get_social_sentiment（免费社交热度代理指标）”，并说明“不含真实评论样本”；
   - 第一部分：热度代理概览（东方财富人气、排名变化、市场参与意愿、关键词、雪球榜单背景）；
   - 第二部分：指标解读（按数据源分类，列出具体数值/状态+可信度+局限）；
   - 第三部分：社交热度周期判断（升温/降温/分歧/信息缺失，并说明依据）；
   - 第四部分：舆情影响评估（短期/长期影响分析+需要后续验证的数据）；
   - 结尾：附加固定格式的Markdown表格（如下），无数据则填“信息缺失”；
2. 报告末尾的固定表格模板（列名不可修改、删减）：

| 舆情维度       | 具体指标               | 量化数值/状态       | 数据来源         | 可信度 | 对股价影响（短期/长期） | 风险提示               |
|----------------|------------------------|---------------------|------------------|--------|------------------------|------------------------|
| 关注热度       | 东方财富人气排名       | [工具返回值/信息缺失] | get_social_sentiment | 中 | 短期波动/长期中性      | 免费热度代理不等于真实情绪 |
| 热度变化       | 人气排名/实时变动      | [工具返回值/信息缺失] | get_social_sentiment | 中 | 短期波动/长期中性      | 排名变化可能快速反转   |
| 参与意愿       | 市场参与意愿           | [工具返回值/信息缺失] | get_social_sentiment | 中 | 短期波动/长期中性      | 参与意愿不是成交确认   |
| 关注质量       | 千股千评关注/综合指标  | [工具返回值/信息缺失] | get_social_sentiment | 中 | 短期参考/长期有限      | 指标口径需保持一致     |
| 关键词热度     | 东方财富热门关键词     | [工具返回值/信息缺失] | get_social_sentiment | 中 | 短期情绪催化/长期中性  | 关键词可能受短期事件驱动 |
| 市场背景       | 雪球关注/讨论榜        | [工具返回值/信息缺失] | get_social_sentiment | 低/中 | 短期背景/长期无直接影响 | 若未命中个股仅作背景   |

【违规处理】
1. 未调用get_social_sentiment工具直接输出 → 输出无效；
2. 编造舆情内容或使用非工具返回数据 → 输出无效；
3. 输出免费接口无法提供的真实评论占比、KOL观点、微博/知乎原文讨论 → 输出无效；
4. 未按规定格式输出（如缺少表格、结构混乱） → 输出无效。
"""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位专业的A股社交热度代理分析师，专注于从公开免费热度指标中识别关注度变化和短期波动风险。"
                    "你的分析将直接作为后续多空辩论的情绪面依据，因此必须明确免费数据边界，避免把热度代理指标说成真实评论情绪。"
                    "使用提供的工具获取数据。如果数据不完整，如实报告即可，严禁编造。"
                    "你可以使用以下工具：{tool_names}。\n{system_message}\n"
                    "当前日期：{current_date}。分析的公司代码：{ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        if len(result.tool_calls) == 0:
            executed_tools = _executed_social_tools(state.get("messages", []))
            missing_tools = [
                name for name in REQUIRED_SOCIAL_TOOLS if name not in executed_tools
            ]
            if missing_tools:
                forced_calls = [
                    _forced_social_tool_call(name, ticker, start_date, end_date)
                    for name in missing_tools
                ]
                return {
                    "messages": [AIMessage(content="", tool_calls=forced_calls)],
                    "sentiment_report": "",
                }

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
