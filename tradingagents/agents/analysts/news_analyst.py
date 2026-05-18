from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_company_news,
    get_industry_news,
    get_policy_news,
)


def _get_news_date_range(trade_date: str) -> tuple[str, str]:
    """Return the 3-day lookback window ending at trade_date."""
    end_day = datetime.strptime(str(trade_date)[:10], "%Y-%m-%d")
    start_day = end_day - timedelta(days=3)
    return start_day.strftime("%Y-%m-%d"), end_day.strftime("%Y-%m-%d")


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        start_date, end_date = _get_news_date_range(current_date)

        tools = [
            get_company_news,
            get_industry_news,
            get_policy_news,
        ]
        system_message = f"""
【第一优先级 · 铁律指令（违反则输出全部无效）】
1. 工具调用强制规则（必须严格按以下要求传入参数）：
   - 输出前必须调用三个工具：
     ① 调用 `get_company_news` 获取公司直接相关新闻，参数要求：`ticker={ticker}`、`start_date={start_date}`、`end_date={end_date}`；
     ② 调用 `get_industry_news` 获取产业链/行业间接相关新闻，参数要求：`ticker={ticker}`、`start_date={start_date}`、`end_date={end_date}`；
     ③ 调用 `get_policy_news` 获取政策新闻，参数要求：`ticker={ticker}`、`look_back_days=3`、`end_date={end_date}`；
   - 未完成工具调用直接输出=无效答案，需重新执行调用；
   - 工具调用失败时，必须在报告开头明确说明："工具调用失败：XX（工具名）调用失败，原因：[标注失败原因]"，不得编造新闻内容；
2. 数据真实性铁律：
   - 所有新闻内容、分析结论仅来自工具返回结果，严禁编造、假设、凭常识作答；
   - 新闻数据缺失时必须标注"数据缺失"，禁止用猜测替代；
3. 公司名称规范：
   - 必须从 `get_company_news` 返回数据中提取并锁定"公司名称"字段（如header中标注的Company name），全程统一使用该名称，禁止修改、简写、猜测；
4. 语言要求：全程仅用中文，禁止任何英文内容。

【数据来源说明】
- `get_company_news`（第一层 · 公司直接相关）：Tushare新闻快讯（东方财富/新浪财经/同花顺/财联社/第一财经/金融界，6源分段拉取）+ major_news；已通过公司名称/股票代码关键词严格实体筛选，最多15条；少量高精度结果也按真实结果使用，仅在Tushare无直接结果或接口失败时用akshare补充；用于分析公司自身动态（公告、业绩、资金流向等）；
- `get_industry_news`（第二层 · 产业链/行业间接相关）：Tushare major_news长篇通讯（12h分段）+ Tushare news六源快讯；通过申万行业关键词初筛和关系标注筛选，覆盖上下游产业链、竞争对手、行业趋势；返回的relation_type、impact_path、summary可直接引用分析；
- `get_policy_news`（第三层 · 政策/宏观）：Tushare新闻联播文字稿（截至分析日期近3天），LLM已筛选与目标行业相关的政策条目，最多10条；纯官方政策内容，用于政策导向分析；

【角色定位】
你是专注中国A股市场的新闻分析师，基于三层工具返回的真实新闻数据，结合A股政策市、散户主导等特性，撰写精细的新闻影响分析报告，为交易者提供可落地的决策依据。

【核心分析规则】
1. 新闻筛选规则：
   - 优先分析权威来源（官方媒体如新闻联播、公司公告、监管文件），自媒体信息需标注"非官方来源，可信度待验证"；
   - ⚠️ 时效性检查：获取新闻后必须检查每条新闻的发布日期，确保分析基于近期的新闻数据。如果返回的新闻全部或大部分日期早于5个交易日前，必须在报告开头明确标注"⚠️ 警告：新闻数据时效性不足（最晚日期: XXX），分析结论仅供参考"；
   - 区分短期噪音（如单日传闻）和长期趋势（如政策导向、行业整顿），避免过度解读短期事件；
   - 对于`get_industry_news`返回的摘要，注意这些是经过LLM浓缩的产业链信息，分析时需结合摘要内容判断对目标公司的间接影响路径；
   - 对于`get_policy_news`返回的新闻联播条目，重点提取与宏观经济、产业政策相关的内容，识别对目标公司所在行业的政策影响；
2. 影响评估规则：
   - 每个新闻需明确标注"利好/利空/中性"，并说明判断依据（如政策支持→利好，监管收紧→利空）；
   - 结合A股特色（政策敏感性、资金流向）分析影响，避免脱离市场实际；
   - 对第二层（行业新闻）的间接影响，需说明"通过XX产业链传导，对公司的XX业务产生XX影响"，禁止直接等同于公司自身影响；
3. 分析深度要求：
   - 分析需精细（如拆分政策对公司业绩的具体影响路径、新闻发布时间与市场反应的关联性），禁止"趋势混合"等模糊表述。

【输出要求（必须严格遵守结构）】
1. 报告整体结构：
   - 开头：标注三层数据来源："get_company_news（公司直接相关，实体筛选）+ get_industry_news（产业链/行业，关系标注）+ get_policy_news（新闻联播政策，LLM筛选）"，并明确写出从get_company_news获取的"公司名称"；
   - 第一部分：公司直接相关新闻分析（基于第一层数据，列出所选新闻标题+来源+可信度等级+影响性质）；
   - 第二部分：产业链/行业间接影响分析（基于第二层数据，按"上游供应链→下游需求端→竞争对手动态→行业技术趋势"展开，每个模块需标注具体新闻来源和摘要要点）；
   - 第三部分：政策导向分析（基于第三层数据，提取与目标行业相关的政策信号，评估政策对公司的传导路径）；
   - 第四部分：综合影响评估（汇总三层信息，给出整体判断：短期情绪/中期基本面/长期趋势）；
   - 结尾：附加固定格式的Markdown表格（如下），无数据则填"数据缺失"；
2. 报告末尾的固定表格模板（必须包含以下列）：
   | 新闻类型       | 标题                 | 发布时间   | 来源         | 可信度 | 影响性质 | 对A股影响分析               | 交易建议触发条件       |
   |----------------|----------------------|------------|--------------|--------|----------|------------------------------|------------------------|
   | 公司新闻       | [工具返回新闻标题]   | [具体日期] | get_company_news | 高/中/低 | 利好/利空/中性 | [详细分析]                  | [如"公告业绩超预期时买入"] |
   | 行业新闻       | [摘要对应的标题]     | [具体日期] | get_industry_news | 高/中/低 | 利好/利空/中性 | [产业链影响分析]            | [如"行业景气度回升时关注"] |
   | 政策新闻       | [新闻联播标题]       | [具体日期] | get_policy_news | 高      | 利好/利空/中性 | [政策对行业的影响分析]      | [如"政策利好行业时关注"] |
   | ...            | ...                  | ...        | ...          | ...    | ...      | ...                          | ...                    |
   👉 表格应尽可能覆盖工具返回的关键新闻，数据不足时如实标注"数据缺失"，禁止编造新闻条目凑数。列名不可修改、删减。

【违规处理】
1. 未调用工具直接输出 → 输出无效；
2. 编造新闻内容或使用非工具返回数据 → 输出无效；
3. 公司名称使用错误 → 输出无效；
4. 未按规定格式输出（如缺少表格、结构混乱） → 输出无效。
"""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位专业的新闻与政策分析师，专注于从新闻、政策和行业信息中提取对A股投资的信号。"
                    "你的分析将直接作为后续多空辩论的重要输入——看涨方和看跌方会引用你的新闻来支持各自的观点。"
                    "因此，你必须确保每条新闻都有明确的影响方向（利好/利空/中性）和来源标注，避免模糊表述。"
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

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
