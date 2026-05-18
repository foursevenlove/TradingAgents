"""Free social-sentiment proxy data built from public AkShare endpoints."""

from __future__ import annotations

import contextlib
import io
from datetime import datetime, timedelta
from typing import Annotated, Optional

import akshare as ak
import pandas as pd

from .akshare_common import _convert_ticker_format, _format_to_csv


def _eastmoney_symbol(ticker: str) -> str:
    stock_code, market = _convert_ticker_format(ticker)
    return f"{market.upper()}{stock_code}"


def _stock_code(ticker: str) -> str:
    stock_code, _ = _convert_ticker_format(ticker)
    return stock_code


def _safe_metric_rows(
    source: str,
    fetcher,
    ticker: str,
    stock_code: str,
    start_date: Optional[str],
    end_date: Optional[str],
    source_targets_ticker: bool = False,
) -> list[dict[str, object]]:
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = fetcher()
        if df is None or df.empty:
            return [
                {
                    "source": source,
                    "metric_name": "status",
                    "ticker": ticker,
                    "stock_code": stock_code,
                    "requested_start_date": start_date or "",
                    "requested_end_date": end_date or "",
                    "data_time": "",
                    "is_in_requested_range": "未知",
                    "is_target_stock": "未知",
                    "current_value": "No data available",
                    "confidence": "低",
                    "limitation": "接口返回空数据",
                }
            ]
        return _rows_from_frame(
            source,
            df,
            ticker,
            stock_code,
            start_date,
            end_date,
            source_targets_ticker=source_targets_ticker,
        )
    except Exception as exc:
        return [
            {
                "source": source,
                "metric_name": "status",
                "ticker": ticker,
                "stock_code": stock_code,
                "requested_start_date": start_date or "",
                "requested_end_date": end_date or "",
                "data_time": "",
                "is_in_requested_range": "未知",
                "is_target_stock": "未知",
                "current_value": "接口失败",
                "confidence": "低",
                "limitation": f"{type(exc).__name__}: {exc}",
            }
        ]


def _extract_row_datetime(row: pd.Series) -> str:
    date_columns = [
        "时间",
        "日期",
        "TRADE_DATE",
        "trade_date",
        "Date",
        "date",
        "datetime",
        "更新时间",
        "发布时间",
        "calcTime",
    ]
    for column in date_columns:
        if column not in row or pd.isna(row[column]):
            continue
        parsed = pd.to_datetime(row[column], errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        return str(row[column])
    return ""


def _maybe_pivot_item_value_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not {"item", "value"}.issubset({str(col) for col in df.columns}):
        return df

    item_col = next(col for col in df.columns if str(col) == "item")
    value_col = next(col for col in df.columns if str(col) == "value")
    record = {}
    for _, row in df.iterrows():
        key = row.get(item_col)
        if pd.isna(key):
            continue
        record[str(key)] = row.get(value_col)
    return pd.DataFrame([record]) if record else df


def _is_in_requested_range(data_time: str, start_date: Optional[str], end_date: Optional[str]) -> str:
    if not data_time or not start_date or not end_date:
        return "未知"
    parsed = pd.to_datetime(data_time, errors="coerce")
    if pd.isna(parsed):
        return "未知"
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return "未知"
    end = end + timedelta(days=1)
    return "是" if start <= parsed < end else "否"


def _row_matches_stock(row: pd.Series, stock_code: str, source_targets_ticker: bool = False) -> str:
    if source_targets_ticker:
        return "是"
    if not stock_code:
        return "未知"
    for value in row.values:
        if pd.isna(value):
            continue
        if stock_code in str(value):
            return "是"
    return "否"


def _confidence_for_row(is_target_stock: str, is_in_requested_range: str) -> str:
    if is_target_stock == "是" and is_in_requested_range in ("是", "未知"):
        return "中"
    if is_target_stock == "否":
        return "低"
    if is_in_requested_range == "否":
        return "低"
    return "中"


def _limitation_for_row(is_target_stock: str, is_in_requested_range: str) -> str:
    limitations = []
    if is_target_stock == "否":
        limitations.append("未直接命中目标股票，仅作市场热度背景")
    elif is_target_stock == "未知":
        limitations.append("无法从该行判断是否命中目标股票")
    if is_in_requested_range == "否":
        limitations.append("数据时间不在请求分析区间内")
    elif is_in_requested_range == "未知":
        limitations.append("该行缺少可解析数据时间")
    return "；".join(limitations) or "免费热度代理指标，不包含真实评论样本"


def _rows_from_frame(
    source: str,
    df: pd.DataFrame,
    ticker: str,
    stock_code: str,
    start_date: Optional[str],
    end_date: Optional[str],
    source_targets_ticker: bool = False,
) -> list[dict[str, object]]:
    rows = []
    df = _maybe_pivot_item_value_frame(df)
    for idx, row in df.iterrows():
        data_time = _extract_row_datetime(row)
        is_in_range = _is_in_requested_range(data_time, start_date, end_date)
        is_target_stock = _row_matches_stock(row, stock_code, source_targets_ticker)
        normalized = {
            "source": source,
            "metric_name": "snapshot" if len(df) == 1 else f"row_{idx}",
            "ticker": ticker,
            "stock_code": stock_code,
            "requested_start_date": start_date or "",
            "requested_end_date": end_date or "",
            "data_time": data_time,
            "is_in_requested_range": is_in_range,
            "is_target_stock": is_target_stock,
            "current_value": "",
            "confidence": _confidence_for_row(is_target_stock, is_in_range),
            "limitation": _limitation_for_row(is_target_stock, is_in_range),
            "raw_row_index": idx,
        }
        for column, value in row.items():
            normalized[str(column)] = "" if pd.isna(value) else value
        rows.append(normalized)
    return rows


def _filter_rank_table(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    code_columns = [col for col in df.columns if "代码" in str(col) or str(col).lower() == "code"]
    if not code_columns:
        return df
    mask = pd.Series(False, index=df.index)
    for col in code_columns:
        mask |= df[col].astype(str).str.contains(stock_code, na=False)
    filtered = df[mask]
    return filtered if not filtered.empty else df


def get_social_sentiment(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Get free A-share social-sentiment proxy metrics.

    The free layer intentionally returns proxy metrics rather than raw user comments:
    Eastmoney popularity ranking, ranking trend, hot keywords, 千股千评 participation
    willingness, and Xueqiu public hot follow/discussion leaderboards.
    """
    stock_code = _stock_code(ticker)
    em_symbol = _eastmoney_symbol(ticker)

    metric_rows: list[dict[str, object]] = []
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富个股人气榜",
            lambda: ak.stock_hot_rank_latest_em(symbol=em_symbol),
            ticker,
            stock_code,
            start_date,
            end_date,
            source_targets_ticker=True,
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富人气实时变动",
            lambda: ak.stock_hot_rank_detail_realtime_em(symbol=em_symbol),
            ticker,
            stock_code,
            start_date,
            end_date,
            source_targets_ticker=True,
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富热门关键词",
            lambda: ak.stock_hot_keyword_em(symbol=em_symbol),
            ticker,
            stock_code,
            start_date,
            end_date,
            source_targets_ticker=True,
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富千股千评",
            lambda: _filter_rank_table(ak.stock_comment_em(), stock_code),
            ticker,
            stock_code,
            start_date,
            end_date,
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富市场参与意愿",
            lambda: ak.stock_comment_detail_scrd_desire_em(symbol=stock_code),
            ticker,
            stock_code,
            start_date,
            end_date,
            source_targets_ticker=True,
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "雪球关注榜",
            lambda: ak.stock_hot_follow_xq(symbol="最热门"),
            ticker,
            stock_code,
            start_date,
            end_date,
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "雪球讨论榜",
            lambda: ak.stock_hot_tweet_xq(symbol="最热门"),
            ticker,
            stock_code,
            start_date,
            end_date,
        )
    )

    df = pd.DataFrame(metric_rows)
    header = "# Free social sentiment proxy\n"
    header += f"# Ticker: {ticker}\n"
    header += f"# Eastmoney symbol: {em_symbol}\n"
    header += f"# Date range requested: {start_date or 'N/A'} to {end_date or 'N/A'}\n"
    header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    header += "# Note: Free public endpoints provide popularity/attention proxies, not raw comment samples.\n"

    return _format_to_csv(df, header)
