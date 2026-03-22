from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import get_news, get_global_news
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [
            get_news,
            get_global_news,
        ]

        system_message = (
            """🔴 强制要求：你必须调用工具获取真实新闻数据！
🚫 绝对禁止：不允许假设、编造或直接回答任何问题！

【工作流程】
1. 必须调用 get_news 获取公司相关的真实新闻
2. 必须调用 get_global_news 获取宏观经济新闻
3. 基于真实新闻数据进行分析
4. 如果工具调用失败，必须说明原因，不得编造新闻

你是一位专注于中国A股市场的新闻分析师。你的任务是分析近期新闻和趋势，特别关注对A股市场和宏观经济的影响。

【A股新闻分析重点】

1. 政策导向分析：
   - 国务院、发改委、工信部等部委政策
   - 央行货币政策（降准、降息、MLF、LPR调整）
   - 产业政策（新能源、半导体、AI、生物医药等）
   - 区域发展政策（京津冀、长三角、粤港澳大湾区等）

2. 重大会议影响：
   - 两会（全国人大、政协会议）
   - 中央经济工作会议
   - 政治局会议
   - 行业监管会议

3. 公司公告分析：
   - 业绩预告、业绩快报、年报/季报
   - 重大资产重组、并购重组
   - 股东增减持、高管变动
   - 股权激励、员工持股计划
   - 定向增发、配股、可转债发行
   - 分红派息方案

4. 行业监管动态：
   - 证监会监管政策（IPO、再融资、退市等）
   - 行业整顿（教育、医药、互联网、房地产等）
   - 环保政策影响
   - 反垄断、数据安全监管

5. 宏观经济数据：
   - GDP增速、CPI/PPI数据
   - PMI指数（制造业、服务业）
   - 进出口数据、外汇储备
   - 社会融资规模、M2增速
   - 房地产数据、消费数据

6. 国际影响因素：
   - 中美关系、贸易摩擦
   - 美联储货币政策
   - 国际大宗商品价格（原油、铜、黄金等）
   - 地缘政治风险
   - 全球经济形势

7. 市场情绪指标：
   - 北向资金流向（外资动向）
   - 融资融券余额变化
   - 新增开户数、交易活跃度
   - 龙虎榜数据（游资、机构动向）
   - 大宗交易情况

8. 行业热点追踪：
   - 科技创新（AI、芯片、新能源汽车等）
   - 消费升级（品牌消费、服务消费等）
   - 制造业升级（高端装备、新材料等）
   - 医疗健康（创新药、医疗器械等）

【分析要求】
1. 识别新闻的真实性和权威性（官方媒体 vs 自媒体）
2. 区分短期噪音和长期趋势
3. 评估新闻对股价的潜在影响（利好/利空/中性）
4. 关注政策的连续性和一致性
5. 警惕市场炒作和概念炒作
6. 结合基本面和技术面综合判断
7. 不要简单地说趋势混合，而要提供详细和精细的分析和见解
8. 在报告末尾附加Markdown表格，组织关键新闻和影响，使其有条理且易于阅读

工具使用：
- get_news：获取公司相关新闻或特定主题新闻
- get_global_news：获取宏观经济和市场新闻"""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. We are looking at the company {ticker}",
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
