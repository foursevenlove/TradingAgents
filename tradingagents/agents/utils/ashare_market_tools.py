from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_north_bound_flow(
    date: Annotated[str, "查询日期，格式：yyyy-mm-dd"] = None,
    look_back_days: Annotated[int, "回溯天数"] = 30,
) -> str:
    """
    获取北向资金流向数据（沪深港通资金流入）。
    北向资金是外资通过沪深港通流入A股的重要指标，反映外资情绪。
    参数：
        date (str): 查询截止日期，格式 yyyy-mm-dd，默认今天
        look_back_days (int): 回溯天数，默认30天
    返回：
        str: 北向资金流向数据
    """
    return route_to_vendor("get_north_bound_flow", date, look_back_days)


@tool
def get_margin_trading(
    ticker: Annotated[str, "股票代码"],
    look_back_days: Annotated[int, "回溯天数"] = 30,
) -> str:
    """
    获取融资融券数据（杠杆资金动向）。
    融资融券数据反映市场杠杆资金动向，融资买入增多表示看多情绪升温。
    参数：
        ticker (str): 股票代码
        look_back_days (int): 回溯天数，默认30天
    返回：
        str: 融资融券数据
    """
    return route_to_vendor("get_margin_trading", ticker, look_back_days)


@tool
def get_limit_up_down_stats(
    date: Annotated[str, "查询日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    获取涨跌停统计数据（市场情绪强度指标）。
    涨停数量远多于跌停表示市场情绪亢奋，反之表示恐慌。
    参数：
        date (str): 查询日期，格式 yyyy-mm-dd，默认今天
    返回：
        str: 涨跌停统计数据
    """
    return route_to_vendor("get_limit_up_down_stats", date)


@tool
def get_dragon_tiger_list(
    date: Annotated[str, "查询日期，格式：yyyy-mm-dd"] = None,
    look_back_days: Annotated[int, "回溯天数"] = 5,
) -> str:
    """
    获取龙虎榜数据（异常交易活动及游资/机构席位追踪）。
    龙虎榜显示出现异常交易活动的股票及买卖席位，可追踪游资和机构动向。
    参数：
        date (str): 查询截止日期，格式 yyyy-mm-dd，默认今天
        look_back_days (int): 回溯天数，默认5天
    返回：
        str: 龙虎榜数据
    """
    return route_to_vendor("get_dragon_tiger_list", date, look_back_days)


@tool
def get_block_trade(
    ticker: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取大宗交易数据（机构大额交易信号）。
    大宗交易通常由机构参与，折价率反映机构对该股的态度。
    参数：
        ticker (str): 股票代码
        start_date (str): 开始日期，格式 yyyy-mm-dd
        end_date (str): 结束日期，格式 yyyy-mm-dd
    返回：
        str: 大宗交易数据
    """
    return route_to_vendor("get_block_trade", ticker, start_date, end_date)


@tool
def get_institutional_holdings(
    ticker: Annotated[str, "股票代码"],
    quarter: Annotated[str, "季度，格式 YYYYQ（如 2024Q3）"] = None,
) -> str:
    """
    获取机构持仓数据（基金/QFII/社保/保险持股明细）。
    机构持仓变化反映专业投资者对该股的中长期看好程度。
    参数：
        ticker (str): 股票代码
        quarter (str): 季度，格式 YYYYQ，如 2024Q3，默认最近一期
    返回：
        str: 机构持仓数据
    """
    return route_to_vendor("get_institutional_holdings", ticker, quarter)