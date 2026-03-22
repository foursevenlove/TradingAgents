from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_stock_data(
    symbol: Annotated[str, "公司的股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取指定股票代码的价格数据（OHLCV）。
    使用配置的核心股票数据源。
    参数：
        symbol (str): 股票代码，例如 000001.SZ, 600000.SH
        start_date (str): 开始日期，格式：yyyy-mm-dd
        end_date (str): 结束日期，格式：yyyy-mm-dd
    返回：
        str: 包含指定日期范围内股票价格数据的格式化数据框。
    """
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)
