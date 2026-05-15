"""Akshare news data implementation for A-share market."""

import re
from datetime import datetime, timedelta
from typing import Annotated, Optional
import akshare as ak
import pandas as pd

from .akshare_common import _convert_ticker_format, _format_to_csv, AkshareDataError

# Industry classification for keyword expansion
try:
    from tradingagents.market_data.industry_classification import get_sw_industry
    INDUSTRY_AVAILABLE = True
except ImportError:
    INDUSTRY_AVAILABLE = False


def _parse_date_from_url(url: str) -> Optional[datetime]:
    """Extract date from East Money news URL.

    URLs like http://finance.eastmoney.com/a/202603163673069 contain
    the date as YYYYMMDD in the path.
    """
    if not url:
        return None
    match = re.search(r"/a/(\d{8})", url)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return None
    return None


def _company_keywords(ticker: str, company_name: Optional[str] = None) -> list[str]:
    stock_code, market = _convert_ticker_format(ticker)
    keywords = [stock_code, f"{stock_code}.{market.upper()}"]
    if company_name:
        keywords.append(company_name)
        short_name = company_name
        for suffix in ["股份有限公司", "有限责任公司", "有限公司", "集团股份", "集团", "控股"]:
            short_name = short_name.replace(suffix, "")
        short_name = short_name.strip()
        if short_name and short_name != company_name:
            keywords.append(short_name)
    return list(dict.fromkeys([kw for kw in keywords if kw]))


def _filter_company_entity_news(df: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    """Filter Akshare company news by title/content, not by the keyword column."""
    if df.empty or not keywords:
        return df.iloc[0:0].copy()

    normalized = [kw.lower() for kw in keywords if kw]
    code_terms = [kw for kw in normalized if re.fullmatch(r"\d{6}", kw)]
    ticker_terms = [kw for kw in normalized if re.fullmatch(r"\d{6}\.(sh|sz)", kw)]
    name_terms = [
        kw for kw in normalized
        if kw not in code_terms and kw not in ticker_terms
    ]

    def matches_row(row):
        text = (
            str(row.get("新闻标题", "")) + " " +
            str(row.get("新闻内容", "")) + " " +
            str(row.get("title", "")) + " " +
            str(row.get("content", ""))
        ).lower()
        if any(keyword in text for keyword in name_terms + ticker_terms):
            return True
        for code in code_terms:
            code_pattern = rf"(股票代码|证券代码|代码)[:：\s]*{code}\b|{code}\.(sh|sz)\b|(sh|sz){code}\b"
            if re.search(code_pattern, text):
                return True
        return False

    return df[df.apply(matches_row, axis=1)].copy()


def get_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Get news for specific A-share stock.

    Args:
        ticker: A-share ticker symbol
        start_date: Start date (optional, not used by akshare)
        end_date: End date (optional, not used by akshare)

    Returns:
        CSV string containing news data

    Note:
        akshare's stock_news_em doesn't support date filtering,
        so start_date and end_date are accepted but ignored for compatibility.
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get stock news from East Money
        # ak.stock_news_em expects format like "600176.SH" or "000001.SZ"
        # so we need to reconstruct the full symbol
        news_symbol = f"{stock_code}.{market.upper()}"
        df = ak.stock_news_em(symbol=news_symbol)

        if df.empty:
            return f"# News for {ticker}\nNo data available"

        company_name = ""
        if INDUSTRY_AVAILABLE:
            try:
                industry_info = get_sw_industry(ticker) or {}
                company_name = industry_info.get("company_name", "")
            except Exception:
                company_name = ""
        keywords = _company_keywords(ticker, company_name)

        # Parse date from URL and sort/filter by date descending to get newest first
        date_range_info = ""
        if "新闻链接" in df.columns:
            df["_parsed_date"] = df["新闻链接"].apply(_parse_date_from_url)
            df["_parsed_date"] = pd.to_datetime(df["_parsed_date"], errors="coerce")
            # Drop rows where date parsing failed
            df = df.dropna(subset=["_parsed_date"])
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                df = df[df["_parsed_date"] >= start_dt]
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                df = df[df["_parsed_date"] <= end_dt]
            # Sort by parsed date descending (newest first)
            df = df.sort_values("_parsed_date", ascending=False)
            df["datetime"] = df["_parsed_date"].dt.strftime("%Y-%m-%d")
            # Record date range before dropping helper column
            dates = df["_parsed_date"]
            if not dates.empty:
                date_range_info = f"# Date range: {dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}\n"
            # Drop the helper column before outputting
            df = df.drop(columns=["_parsed_date"])

        total_after_date = len(df)
        df = _filter_company_entity_news(df, keywords)

        df = df.rename(columns={
            "新闻标题": "title",
            "新闻内容": "content",
            "发布时间": "pub_time",
            "文章来源": "data_source",
            "新闻链接": "url",
            "关键词": "source_keyword",
        })

        # Limit to top 20 most recent items
        df = df.head(20)

        header = f"# News for {ticker}\n"
        header += f"# Company name: {company_name or 'N/A'}\n"
        header += f"# Keywords: {keywords}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Date-filtered raw: {total_after_date} | Entity filtered: {len(df)}\n"
        header += f"# Total items: {len(df)}\n"
        if date_range_info:
            header += date_range_info

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get news for {ticker}: {str(e)}")


def get_global_news(
    curr_date: Optional[str] = None,
    look_back_days: Optional[int] = None,
    limit: Optional[int] = None,
    ticker: Optional[str] = None,
) -> str:
    """Get global financial news relevant to A-share market.

    Uses 财联社 (cls) financial news + 新闻联播 (CCTV) macro policy news.
    The former Baidu finance API (news_economic_baidu) has been discontinued.

    Args:
        curr_date: Current date (optional)
        look_back_days: Number of days to look back (optional)
        limit: Maximum number of news items to return (default: 20)

    Returns:
        CSV string containing global news data
    """
    try:
        all_news = []

        # Source 1: 财联社 (CLS) - real-time financial news feed
        try:
            df_cls = ak.stock_info_global_cls()
            if not df_cls.empty:
                # Rename columns to consistent format
                df_cls = df_cls.rename(columns={
                    "标题": "Title",
                    "内容": "Content",
                    "发布日期": "Date",
                    "发布时间": "Time",
                })
                all_news.append(df_cls)
        except Exception:
            pass  # CLS may be temporarily unavailable

        # Source 2: 新闻联播 (CCTV) - macro policy news, very important for A-share policy analysis
        if curr_date is not None:
            cctv_date = curr_date.replace("-", "")
            try:
                df_cctv = ak.news_cctv(date=cctv_date)
                if not df_cctv.empty:
                    df_cctv = df_cctv.rename(columns={
                        "date": "Date",
                        "title": "Title",
                        "content": "Content",
                    })
                    df_cctv["Source"] = "CCTV新闻联播"
                    all_news.append(df_cctv)
            except Exception:
                pass  # CCTV data may not be available for this date yet

        if not all_news:
            return "No global news available (CLS and CCTV sources temporarily unavailable)"

        df = pd.concat(all_news, ignore_index=True)

        # Limit output
        max_items = limit if limit is not None else 20
        df = df.head(max_items)

        header = f"# Global financial news (财联社 + 新闻联播)\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(df)}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        return f"No global news available ({str(e)})"


def get_insider_transactions(
    ticker: Annotated[str, "A-share ticker symbol"],
) -> str:
    """Get insider transactions (shareholder changes) for A-share stocks.

    Args:
        ticker: A-share ticker symbol

    Returns:
        CSV string containing insider transaction data
    """
    try:
        stock_code, market = _convert_ticker_format(ticker)

        # Get shareholder changes
        # ak.stock_zh_a_gdhs returns shareholder change data
        df = ak.stock_zh_a_gdhs(symbol=stock_code)

        if df.empty:
            return f"No insider transaction data found for {ticker}"

        header = f"# Insider transactions for {ticker}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return _format_to_csv(df, header)

    except Exception as e:
        raise AkshareDataError(f"Failed to get insider transactions for {ticker}: {str(e)}")


def get_company_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """第一层 fallback：akshare 公司新闻。

    委托给现有 get_news()，功能不变。
    """
    return get_news(ticker, start_date, end_date)


def get_industry_news(
    ticker: Annotated[str, "A-share ticker symbol"],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """第二层 fallback：akshare 行业/产业链新闻。

    调用 ak.stock_info_global_cls()，通过行业关键词过滤，
    返回最多 20 条（fallback 层不做 LLM 摘要）。
    """
    try:
        # 获取行业分类
        industry_info = {}
        if INDUSTRY_AVAILABLE:
            try:
                industry_info = get_sw_industry(ticker) or {}
            except Exception:
                pass

        level_1 = industry_info.get('level_1', '')
        level_2 = industry_info.get('level_2', '')
        industry_keywords = [kw for kw in [level_1, level_2] if kw and kw != '未知']
        industry_context = ' / '.join(industry_keywords) if industry_keywords else '未知行业'

        # 财联社全球财经新闻
        df = ak.stock_info_global_cls()
        if df.empty:
            return f"# 第二层 · 产业链/行业新闻 ({ticker}) — akshare fallback\nNo data available\n"

        # 重命名列
        df = df.rename(columns={
            "标题": "title",
            "内容": "content",
            "发布日期": "Date",
            "发布时间": "Time",
        })
        df['data_source'] = 'akshare_cls'

        if start_date or end_date:
            date_col = "Date" if "Date" in df.columns else None
            if date_col:
                parsed_dates = pd.to_datetime(df[date_col], errors="coerce")
                mask = parsed_dates.notna()
                if start_date:
                    mask &= parsed_dates >= pd.to_datetime(start_date)
                if end_date:
                    mask &= parsed_dates <= pd.to_datetime(end_date)
                df = df[mask].copy()

        # 行业关键词过滤
        if industry_keywords:
            keywords_lower = [k.lower() for k in industry_keywords]
            mask = df.apply(
                lambda r: any(kw in str(r.get('title', '')).lower() + str(r.get('content', '')).lower()
                             for kw in keywords_lower),
                axis=1
            )
            filtered = df[mask]
        else:
            filtered = df

        # 最多 20 条
        final_df = filtered.head(20)

        header = f"# 第二层 · 产业链/行业新闻 ({ticker}) — akshare fallback\n"
        header += f"# Industry: {industry_context}\n"
        header += f"# Total: {len(df)} | Filtered: {len(filtered)} | Final: {len(final_df)}\n"
        header += f"# Note: Fallback data, no LLM summarization\n"

        return _format_to_csv(final_df, header)

    except Exception as e:
        return f"# 第二层 · 产业链/行业新闻 ({ticker}) — akshare fallback\n# Error: {str(e)}\n"


def get_policy_news(
    ticker: Annotated[str, "A-share ticker symbol"],
    look_back_days: Annotated[int, "回溯天数"] = 3,
    end_date: Annotated[str, "截止日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """第三层 fallback：akshare 政策新闻。

    调用 ak.news_cctv() 返回全量（fallback 层不做 LLM 筛选）。
    """
    try:
        all_cctv = []
        if end_date:
            end_day = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_day = datetime.now()

        for i in range(look_back_days):
            date = end_day - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            try:
                df = ak.news_cctv(date=date_str)
                if not df.empty:
                    df['retrieved_date'] = date.strftime("%Y-%m-%d")
                    all_cctv.append(df)
            except Exception:
                continue

        if not all_cctv:
            header = f"# 第三层 · 政策新闻 ({ticker}) — akshare fallback\n"
            header += f"# Date range: {(end_day - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {end_day.strftime('%Y-%m-%d')}\n"
            header += "No data available\n"
            return header

        merged = pd.concat(all_cctv, ignore_index=True)

        header = f"# 第三层 · 政策新闻 ({ticker}) — akshare fallback\n"
        header += f"# Date range: {(end_day - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {end_day.strftime('%Y-%m-%d')}\n"
        header += f"# Total items: {len(merged)}\n"
        header += f"# Note: Fallback data, no LLM filtering\n"

        return _format_to_csv(merged, header)

    except Exception as e:
        return f"# 第三层 · 政策新闻 ({ticker}) — akshare fallback\n# Error: {str(e)}\n"


def get_recommendation_news(
    look_back_days: Annotated[int, "回溯天数"] = 1,
    max_articles: Annotated[int, "返回的最大新闻数量"] = 1000,
) -> str:
    """推荐系统热点新闻的 akshare fallback。

    聚合财联社快讯 + 新闻联播，不做关键词过滤。
    """
    try:
        all_news = []
        today = datetime.now()

        # 1. 财联社快讯
        try:
            df_cls = ak.stock_info_global_cls()
            if not df_cls.empty:
                df_cls = df_cls.rename(columns={
                    "标题": "title",
                    "内容": "content",
                    "发布日期": "Date",
                    "发布时间": "Time",
                })
                df_cls['data_source'] = 'akshare_cls'
                all_news.append(df_cls)
        except Exception:
            pass

        # 2. 新闻联播
        for i in range(look_back_days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            try:
                df_cctv = ak.news_cctv(date=date_str)
                if not df_cctv.empty:
                    df_cctv = df_cctv.rename(columns={
                        "date": "datetime",
                        "title": "title",
                        "content": "content",
                    })
                    df_cctv['data_source'] = 'akshare_cctv'
                    all_news.append(df_cctv)
            except Exception:
                continue

        if not all_news:
            return f"# 推荐系统热点新闻 — akshare fallback\n# No news available\n"

        merged = pd.concat(all_news, ignore_index=True)
        merged = merged.drop_duplicates(subset=['title'], keep='first')

        # 清理content
        if 'content' in merged.columns:
            merged['content'] = merged['content'].apply(lambda x: re.sub(r'<[^>]+>', '', str(x)) if x else '')

        final = merged.head(max_articles)

        header = f"# 推荐系统热点新闻 — akshare fallback\n"
        header += f"# Date range: {(today - timedelta(days=look_back_days)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}\n"
        header += f"# Total: {len(final)} articles\n"
        header += f"# Note: Fallback data (tushare primary)\n"

        output_cols = ['title', 'content', 'datetime', 'data_source']
        available_cols = [c for c in output_cols if c in final.columns]
        if available_cols:
            final = final[available_cols]

        return _format_to_csv(final, header)

    except Exception as e:
        return f"# 推荐系统热点新闻 — akshare fallback\n# Error: {str(e)}\n"
