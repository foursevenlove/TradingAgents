from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_social_sentiment(
    ticker: Annotated[str, "股票代码"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"],
) -> str:
    """
    获取免费社交舆情代理指标。

    数据来自公开免费接口，包含东方财富人气/千股千评/市场参与意愿、
    雪球关注榜/讨论榜等热度代理指标；不包含真实评论样本或精确评论占比。
    """
    return route_to_vendor("get_social_sentiment", ticker, start_date, end_date)
