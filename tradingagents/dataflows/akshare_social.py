"""Free social-sentiment proxy data built from public AkShare endpoints."""

from __future__ import annotations

import contextlib
import io
from datetime import datetime
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


def _safe_metric_rows(source: str, fetcher) -> list[dict[str, object]]:
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = fetcher()
        if df is None or df.empty:
            return [
                {
                    "source": source,
                    "metric": "status",
                    "value": "No data available",
                    "detail": "",
                    "confidence": "低",
                }
            ]
        return _rows_from_frame(source, df)
    except Exception as exc:
        return [
            {
                "source": source,
                "metric": "status",
                "value": "接口失败",
                "detail": f"{type(exc).__name__}: {exc}",
                "confidence": "低",
            }
        ]


def _rows_from_frame(source: str, df: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    limited = df.head(5).copy()
    for idx, row in limited.iterrows():
        details = []
        for column, value in row.items():
            if pd.isna(value):
                continue
            details.append(f"{column}={value}")
        rows.append(
            {
                "source": source,
                "metric": f"row_{idx}",
                "value": "; ".join(details[:4]),
                "detail": "; ".join(details[4:10]),
                "confidence": "中",
            }
        )
    return rows


def _filter_rank_table(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    code_columns = [col for col in df.columns if "代码" in str(col) or str(col).lower() == "code"]
    if not code_columns:
        return df.head(5)
    mask = pd.Series(False, index=df.index)
    for col in code_columns:
        mask |= df[col].astype(str).str.contains(stock_code, na=False)
    filtered = df[mask]
    return filtered if not filtered.empty else df.head(5)


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
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富人气实时变动",
            lambda: ak.stock_hot_rank_detail_realtime_em(symbol=em_symbol),
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富热门关键词",
            lambda: ak.stock_hot_keyword_em(symbol=em_symbol),
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富千股千评",
            lambda: _filter_rank_table(ak.stock_comment_em(), stock_code),
        )
    )
    metric_rows.extend(
        _safe_metric_rows(
            "东方财富市场参与意愿",
            lambda: ak.stock_comment_detail_scrd_desire_em(symbol=stock_code),
        )
    )
    metric_rows.extend(
        _safe_metric_rows("雪球关注榜", lambda: ak.stock_hot_follow_xq(symbol="最热门"))
    )
    metric_rows.extend(
        _safe_metric_rows("雪球讨论榜", lambda: ak.stock_hot_tweet_xq(symbol="最热门"))
    )

    df = pd.DataFrame(metric_rows)
    header = "# Free social sentiment proxy\n"
    header += f"# Ticker: {ticker}\n"
    header += f"# Eastmoney symbol: {em_symbol}\n"
    header += f"# Date range requested: {start_date or 'N/A'} to {end_date or 'N/A'}\n"
    header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    header += "# Note: Free public endpoints provide popularity/attention proxies, not raw comment samples.\n"

    return _format_to_csv(df, header)
