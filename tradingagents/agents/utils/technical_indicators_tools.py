from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_indicators(
    symbol: Annotated[str, "公司的股票代码"],
    indicator: Annotated[str, "要获取的技术指标名称"],
    curr_date: Annotated[str, "当前交易日期，格式：YYYY-mm-dd"],
    look_back_days: Annotated[int, "回溯天数"] = 30,
) -> str:
    """
    获取指定股票代码的单个技术指标。
    使用配置的技术指标数据源。
    参数：
        symbol (str): 股票代码，例如 000001.SZ, 600000.SH
        indicator (str): 单个技术指标名称，例如 'rsi', 'macd'。每次调用此工具只能查询一个指标。
        curr_date (str): 当前交易日期，格式：YYYY-mm-dd
        look_back_days (int): 回溯天数，默认为30天
    返回：
        str: 包含指定股票代码和指标的格式化数据框。
    """
    # LLMs sometimes pass multiple indicators as a comma-separated string;
    # split and process each individually.
    indicators = [i.strip() for i in indicator.split(",") if i.strip()]
    if len(indicators) > 1:
        results = []
        for ind in indicators:
            results.append(route_to_vendor("get_indicators", symbol, ind, curr_date, look_back_days))
        return "\n\n".join(results)
    return route_to_vendor("get_indicators", symbol, indicator.strip(), curr_date, look_back_days)