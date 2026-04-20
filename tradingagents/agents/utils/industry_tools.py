from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_sw_industry(
    ticker: Annotated[str, "股票代码"],
) -> str:
    """
    获取股票的申万行业分类（一级行业、二级行业、三级行业）。
    申万行业分类是A股市场的标准分类体系，用于判断股票所属行业板块。
    参数：
        ticker (str): 股票代码
    返回：
        str: 申万行业分类信息
    """
    return route_to_vendor("get_sw_industry", ticker)


@tool
def get_industry_peers(
    ticker: Annotated[str, "股票代码"],
    limit: Annotated[int, "返回的最大同行数量"] = 10,
) -> str:
    """
    获取同行业股票列表（同板块竞争对手/可比公司）。
    用于横向比较分析，了解该股在行业中的相对位置。
    参数：
        ticker (str): 股票代码
        limit (int): 返回的最大同行数量，默认10家
    返回：
        str: 同行业股票列表
    """
    return route_to_vendor("get_industry_peers", ticker, limit)


@tool
def get_industry_performance(
    industry_name: Annotated[str, "行业名称（如银行、计算机应用）"],
    look_back_days: Annotated[int, "回溯天数"] = 30,
) -> str:
    """
    获取行业板块表现统计（行业平均涨跌幅、换手率、涨跌排名）。
    用于判断当前行业板块的整体强弱，辅助板块轮动分析。
    参数：
        industry_name (str): 行业名称，如"银行"、"计算机应用"
        look_back_days (int): 回溯天数，默认30天
    返回：
        str: 行业板块表现统计
    """
    return route_to_vendor("get_industry_performance", industry_name, look_back_days)