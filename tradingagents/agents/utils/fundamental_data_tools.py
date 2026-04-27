from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_fundamentals(
    ticker: Annotated[str, "股票代码"],
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取指定股票代码的综合基本面数据。
    使用配置的基本面数据源。
    参数：
        ticker (str): 股票代码
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含综合基本面数据的格式化报告
    """
    return route_to_vendor("get_fundamentals", ticker, curr_date)


@tool
def get_balance_sheet(
    ticker: Annotated[str, "股票代码"],
    freq: Annotated[str, "报告频率：annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    获取指定股票代码的资产负债表数据。
    使用配置的基本面数据源。
    参数：
        ticker (str): 股票代码
        freq (str): 报告频率：annual（年报）/quarterly（季报），默认为季报
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含资产负债表数据的格式化报告
    """
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


@tool
def get_cashflow(
    ticker: Annotated[str, "股票代码"],
    freq: Annotated[str, "报告频率：annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    获取指定股票代码的现金流量表数据。
    使用配置的基本面数据源。
    参数：
        ticker (str): 股票代码
        freq (str): 报告频率：annual（年报）/quarterly（季报），默认为季报
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含现金流量表数据的格式化报告
    """
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


@tool
def get_income_statement(
    ticker: Annotated[str, "股票代码"],
    freq: Annotated[str, "报告频率：annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "当前交易日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """
    获取指定股票代码的利润表数据。
    使用配置的基本面数据源。
    参数：
        ticker (str): 股票代码
        freq (str): 报告频率：annual（年报）/quarterly（季报），默认为季报
        curr_date (str): 当前交易日期，格式：yyyy-mm-dd
    返回：
        str: 包含利润表数据的格式化报告
    """
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)


@tool
def get_pledge_ratio(
    ticker: Annotated[str, "股票代码"],
) -> str:
    """
    获取指定股票代码的股权质押比例数据。
    股权质押比例是股东质押股份占总股本的比例，高质押比例可能带来风险。
    使用akshare数据源（仅akshare支持）。
    参数：
        ticker (str): 股票代码
    返回：
        str: 包含股权质押数据的格式化报告
    """
    return route_to_vendor("get_pledge_ratio", ticker)