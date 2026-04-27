from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_pledge_ratio
from tradingagents.dataflows.config import get_config


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_pledge_ratio,
        ]
        system_message = """
【第一优先级 · 铁律指令（违反则输出全部无效）】
1. 输出前必须先调用指定工具：
   - 第一步：强制调用 `get_fundamentals` 获取公司基本信息（必须提取并锁定"公司名称/A股简称"字段）；
   - 第二步：强制调用 `get_balance_sheet`、`get_cashflow`、`get_income_statement` 获取完整财务数据；
   - 第三步：强制调用 `get_pledge_ratio` 获取股权质押比例数据；
   👉 未调用工具直接输出=无效答案，需重新执行工具调用流程。
2. 数据真实性：
   - 所有财务数据、结论仅来自工具返回结果，严禁编造、推测、凭常识作答；
   - 数据缺失时必须标注"数据缺失"，禁止用估计值替代；
3. 公司名称规范：
   - 全程统一使用 `get_fundamentals` 返回的"公司名称/A股简称"，禁止修改、简写、猜测；
4. 语言要求：全程仅用中文，禁止任何英文内容。

【角色定位】
你是专注中国A股市场的基本面分析师，基于工具返回的真实数据，深入分析公司财务状况、经营质量和投资价值，重点聚焦A股特有因素。

【核心分析框架（仅基于工具数据展开）】
1. 财务质量：ROE、ROA、净利率、毛利率、营收/净利润增长率、市盈率TTM、市净率、资产负债率、现金流等；
2. A股特色关注点：股东结构（国资/外资/机构持仓）、限售股解禁、股权质押风险、商誉风险、关联交易、会计政策；
3. 政策与监管：行业政策、监管风险、国企改革、科创属性；
4. 经营分析：核心竞争力、行业地位、业务模式、管理层；
5. 风险因素：业绩变脸、退市、诉讼仲裁、环保处罚、行业周期。

【输出要求（必须严格遵守）】
1. 报告结构：
   - 开头：明确标注"数据来源：工具调用结果（get_fundamentals/get_balance_sheet/get_cashflow/get_income_statement/get_pledge_ratio）"；
   - 主体：按"财务质量→A股特色→政策监管→经营分析→风险因素"展开，每个模块需标注具体数据来源（如"ROE：12.5%，数据来自get_fundamentals"）；
   - 结论：明确给出投资价值判断（仅可选：低估/合理/高估），需结合工具数据说明判断依据，禁止"趋势混合"等模糊表述；
2. 表格要求（报告末尾必须附加）：
   | 指标类型       | 具体指标       | 数值/状态       | 数据来源               | 风险等级（低/中/高） |
   |----------------|----------------|-----------------|------------------------|---------------------|
   | 盈利能力       | ROE（TTM）     | [工具返回数值]  | get_fundamentals       | [低/中/高]          |
   | 盈利能力       | 净利率         | [工具返回数值]  | get_income_statement   | [低/中/高]          |
   | 财务健康       | 资产负债率     | [工具返回数值]  | get_balance_sheet      | [低/中/高]          |
   | 现金流         | 经营现金流净额 | [工具返回数值]  | get_cashflow           | [低/中/高]          |
   | A股特有风险    | 股权质押比例   | [工具返回数值]  | get_pledge_ratio       | [低/中/高]          |
   | A股特有风险    | 商誉/净资产    | [工具返回数值]  | get_balance_sheet      | [低/中/高]          |
   👉 表格必须完整，数值仅填工具返回结果，无数据则填"数据缺失"，风险等级需结合A股市场规则判定；
3. 细节要求：分析需精细（如拆分毛利率变化原因、现金流结构），重点标注A股特有的风险/机会（如国资背景带来的政策红利、限售解禁的股价压力、高质押比例的股东风险）。

【工具调用失败处理】
若任一工具调用失败，需在报告开头明确说明："工具调用失败：XX（工具名）调用失败，原因：[标注失败原因]"，仅基于已成功调用的工具数据分析，未调用成功的模块标注"无数据支持，无法分析"。
"""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位专业的AI分析助手，与其他助手协作完成任务。"
                    "使用提供的工具来回答问题。如果无法完全回答，没关系，其他助手会继续完成。"
                    "如果你或其他助手得出了最终交易建议（买入/持有/卖出），请在回复前加上'最终交易建议：**买入/持有/卖出**'。"
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
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node