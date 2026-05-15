from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_news(
    ticker: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取指定股票代码的新闻数据。
    使用配置的新闻数据源（tushare关键词筛选 + akshare补充）。
    参数：
        ticker (str): 股票代码
        start_date (str): 开始日期，格式：yyyy-mm-dd
        end_date (str): 结束日期，格式：yyyy-mm-dd
    返回：
        str: 包含新闻数据的格式化字符串
    """
    return route_to_vendor("get_news", ticker, start_date, end_date)

@tool
def get_global_news(
    curr_date: Annotated[str, "当前日期，格式：yyyy-mm-dd"],
    look_back_days: Annotated[int, "回溯天数"] = 7,
    limit: Annotated[int, "返回的最大文章数"] = 200,
    ticker: Annotated[str, "股票代码（用于行业相关性筛选）"] = "",
) -> str:
    """
    获取全球财经新闻数据。
    使用配置的新闻数据源（tushare华尔街见闻/云财经 + akshare财联社/CCTV补充）。
    当传入ticker时，会优先筛选与该股票行业相关的新闻，不足时用LLM语义补充。
    参数：
        curr_date (str): 当前日期，格式：yyyy-mm-dd
        look_back_days (int): 回溯天数，默认为7天
        limit (int): 返回的最大文章数，默认为200篇
        ticker (str): 股票代码，用于行业相关性筛选
    返回：
        str: 包含全球新闻数据的格式化字符串
    """
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit, ticker)

@tool
def get_cctv_news(
    look_back_days: Annotated[int, "回溯天数，默认3天"] = 3,
) -> str:
    """
    获取新闻联播文字稿数据。
    调用tushare的cctv_news接口，获取近几天的新闻联播完整文字稿。
    用于宏观政策分析，包含国家政策、宏观战略等官方信息。
    参数：
        look_back_days (int): 回溯天数，默认为3天
    返回：
        str: 包含新闻联播文字稿的格式化字符串
    """
    return route_to_vendor("get_cctv_news", look_back_days)

@tool
def get_insider_transactions(
    ticker: Annotated[str, "股票代码"],
) -> str:
    """
    获取公司的内部交易（股东增减持）信息。
    使用配置的新闻数据源。
    参数：
        ticker (str): 票代码
    返回：
        str: 内部交易数据报告
    """
    return route_to_vendor("get_insider_transactions", ticker)


@tool
def get_company_news(
    ticker: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    第一层：获取公司直接相关新闻。
    调用 tushare news API（6源分段拉取）+ major_news 长篇通讯，
    通过公司名+股票代码严格实体筛选，最多返回 20 条。
    已预过滤，结果均为与公司直接相关的新闻快讯。
    参数：
        ticker (str): 股票代码
        start_date (str): 开始日期，格式：yyyy-mm-dd，默认3天前
        end_date (str): 结束日期，格式：yyyy-mm-dd，默认当天
    返回：
        str: 包含公司直接相关新闻的格式化字符串（CSV格式）
    """
    return route_to_vendor("get_company_news", ticker, start_date, end_date)


@tool
def get_industry_news(
    ticker: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    第二层：获取产业链/行业间接相关新闻。
    调用 tushare major_news（长篇通讯，12h分段）+ tushare news 六源快讯，
    通过行业关键词初筛、确定性排序和关系标注筛选。
    覆盖上下游产业链、竞争对手、行业趋势等相关信息。
    参数：
        ticker (str): 股票代码
        start_date (str): 开始日期，格式：yyyy-mm-dd，默认3天前
        end_date (str): 结束日期，格式：yyyy-mm-dd，默认当天
    返回：
        str: 包含产业链/行业新闻的格式化字符串（CSV格式，含summary列）
    """
    return route_to_vendor("get_industry_news", ticker, start_date, end_date)


@tool
def get_policy_news(
    ticker: Annotated[str, "股票代码"],
    look_back_days: Annotated[int, "回溯天数，默认3天"] = 3,
    end_date: Annotated[str, "截止日期，格式：yyyy-mm-dd；默认当天"] = None,
) -> str:
    """
    第三层：获取政策/宏观新闻。
    调用 tushare cctv_news API，拉取新闻联播文字稿，
    通过 LLM 筛选与目标股票行业相关的政策条目。
    参数：
        ticker (str): 股票代码
        look_back_days (int): 回溯天数，默认为3天
        end_date (str): 截止日期，格式：yyyy-mm-dd，默认当天
    返回：
        str: 包含政策新闻的格式化字符串（CSV格式）
    """
    return route_to_vendor("get_policy_news", ticker, look_back_days, end_date)
