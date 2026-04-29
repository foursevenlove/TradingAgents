"""Tushare Pro news data implementation.

Provides news data from Tushare Pro API, with multiple data source support
and intelligent filtering for stock-specific news.

Requires:
    - tushare package (pip install tushare)
    - TUSHARE_TOKEN environment variable (get from https://tushare.pro)
    - Separate permission for news/major_news/cctv_news interfaces
"""

import os
import re
from datetime import datetime, timedelta
from typing import Annotated, Optional, List
import pandas as pd

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

# Lazy-loaded LLM for news filtering (used when keyword filtering yields insufficient results)
_FILTER_LLM = None


def _get_filter_llm():
    """Get a lightweight LLM instance for semantic news filtering."""
    global _FILTER_LLM
    if _FILTER_LLM is None:
        try:
            from tradingagents.llm_clients.factory import create_llm_client
            from tradingagents.llm_clients.validators import get_default_settings
            settings = get_default_settings()
            provider = settings.get("provider", "minimax")
            model = settings.get("quick_think_llm", "MiniMax-M2.5")
            client = create_llm_client(provider, model)
            _FILTER_LLM = client.get_llm()
        except Exception:
            _FILTER_LLM = None
    return _FILTER_LLM


class TushareDataError(Exception):
    """Exception raised for Tushare data errors."""
    pass


def _get_pro_api():
    """Get Tushare Pro API instance.

    Token is read from TUSHARE_TOKEN environment variable.
    """
    if not TUSHARE_AVAILABLE:
        raise TushareDataError(
            "tushare package not installed. Install with: pip install tushare"
        )

    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise TushareDataError(
            "TUSHARE_TOKEN not set. Get your token from https://tushare.pro "
            "and set it in .env or environment variable."
        )

    return ts.pro_api(token)


def _convert_ticker_to_tushare(symbol: str) -> str:
    """Convert ticker format to Tushare format (e.g., 000001.SZ).

    Tushare uses the same format as the existing akshare convention.
    """
    symbol = symbol.upper().strip()
    if "." in symbol:
        return symbol

    # Infer market from code prefix
    if symbol.startswith(("000", "002", "300")):
        return f"{symbol}.SZ"
    elif symbol.startswith(("600", "601", "603", "688")):
        return f"{symbol}.SH"
    else:
        return f"{symbol}.SZ"


def _get_stock_name_from_code(stock_code: str) -> Optional[str]:
    """Get stock name from stock code for keyword filtering.

    Uses tushare's stock_basic interface to get the company name.
    """
    try:
        pro = _get_pro_api()
        # Convert code to ts_code format
        ts_code = _convert_ticker_to_tushare(stock_code)
        df = pro.stock_basic(ts_code=ts_code, fields='ts_code,name')
        if not df.empty:
            return df.iloc[0]['name']
    except Exception:
        pass
    return None


def _format_to_csv(df: pd.DataFrame, header_info: Optional[str] = None) -> str:
    """Format DataFrame to CSV string with optional header."""
    if df.empty:
        return "No data available"

    csv_string = df.to_csv(index=False)

    if header_info:
        return header_info + "\n" + csv_string

    return csv_string


def _filter_by_keywords(df: pd.DataFrame, keywords: List[str]) -> pd.DataFrame:
    """Filter news DataFrame by keywords in title or content.

    Args:
        df: News DataFrame with 'title' and optionally 'content' columns
        keywords: List of keywords to search for (e.g., company name, stock code)

    Returns:
        Filtered DataFrame containing only rows matching any keyword
    """
    if df.empty or not keywords:
        return df

    # Build search pattern
    keywords_lower = [k.lower() for k in keywords]

    def matches_row(row):
        title = str(row.get('title', '')).lower()
        content = str(row.get('content', '')).lower()

        for keyword in keywords_lower:
            if keyword in title or keyword in content:
                return True
        return False

    # Filter rows
    mask = df.apply(matches_row, axis=1)
    filtered_df = df[mask]

    return filtered_df


def _llm_select_relevant_news(
    ticker: str,
    company_name: str,
    candidates_df: pd.DataFrame,
    target_count: int,
) -> List[int]:
    """Use LLM to select the most relevant news indices from candidates.

    When keyword filtering yields insufficient results, this function uses
    semantic understanding to identify news that is relevant to the target
    company even if the title/content doesn't contain the exact keywords.

    Returns a list of DataFrame index values (not row positions).
    """
    if candidates_df.empty or target_count <= 0:
        return []

    llm = _get_filter_llm()
    if llm is None:
        # Fallback: return first N candidates by index
        return candidates_df.head(target_count).index.tolist()

    # Build numbered candidate list (limit to 150 to control token usage)
    candidate_rows = candidates_df.head(150)
    lines = []
    index_map = {}  # Maps display number -> original DataFrame index
    for display_num, (orig_idx, row) in enumerate(candidate_rows.iterrows(), 1):
        index_map[display_num] = orig_idx
        title = str(row.get('title', ''))[:120]
        date = str(row.get('datetime', row.get('pub_time', '')))[:19]
        source = str(row.get('data_source', ''))
        content = str(row.get('content', ''))[:200]
        lines.append(
            f"{display_num}. [{date}] 来源:{source}\n"
            f"   标题:{title}\n"
            f"   摘要:{content}"
        )

    candidate_text = "\n\n".join(lines)

    prompt = f"""从以下新闻候选列表中，选出与【{company_name}({ticker})】最相关的{target_count}条新闻。

相关性判断标准（按优先级）：
1. 直接提到公司名或股票代码 → 最优先保留
2. 提到公司所在行业且对公司有实质影响 → 优先保留
3. 宏观政策对公司业务有直接影响 → 可考虑保留
4. 涉及公司主要竞争对手或上下游产业链 → 弱相关，仅在没有更相关新闻时保留
5. 与该公司明显无关的新闻 → 排除

只返回编号列表，格式如：1,3,7,12,15
不要添加任何解释或额外文字。

候选新闻：
{candidate_text}
"""

    try:
        result = llm.invoke(prompt)
        content = result.content if hasattr(result, 'content') else str(result)
        # Parse numbers from response
        numbers = re.findall(r'\d+', content)
        selected = []
        seen = set()
        for n_str in numbers:
            n = int(n_str)
            if n in index_map and n not in seen:
                seen.add(n)
                selected.append(index_map[n])
        return selected[:target_count]
    except Exception:
        # Fallback: return first N candidates by index
        return candidates_df.head(target_count).index.tolist()


def get_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """Get news for specific A-share stock using Tushare Pro.

    Strategy:
    1. Call tushare news API with multiple data sources (eastmoney, sina, 10jqka, cls, yicai, jinrongjie)
    2. Filter results by company name and stock code keywords
    3. If filtered results < 5, fallback to akshare stock_news_em (which supports stock code query)

    Args:
        ticker: A-share ticker symbol
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string containing filtered news data relevant to the stock
    """
    try:
        pro = _get_pro_api()
        stock_code = _convert_ticker_to_tushare(ticker)

        # Get company name for keyword filtering
        company_name = _get_stock_name_from_code(ticker)
        keywords = [stock_code.split('.')[0]]  # Stock code without market suffix
        if company_name:
            keywords.append(company_name)

        # Set default date range
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # Format dates for Tushare API (requires datetime format)
        start_dt = f"{start_date} 00:00:00"
        end_dt = f"{end_date} 23:59:59"

        # Data sources for company-specific news (per user's specification)
        company_news_sources = ['eastmoney', 'sina', '10jqka', 'cls', 'yicai', 'jinrongjie']

        all_news = []

        # Collect news from each source
        for src in company_news_sources:
            try:
                df = pro.news(src=src, start_date=start_dt, end_date=end_dt)
                if not df.empty:
                    # Add source identifier
                    df['data_source'] = src
                    all_news.append(df)
            except Exception:
                # Some sources may be temporarily unavailable, continue with others
                continue

        # Merge all news
        if all_news:
            merged_df = pd.concat(all_news, ignore_index=True)
            # Deduplicate by title
            merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')

            # Filter by keywords
            filtered_df = _filter_by_keywords(merged_df, keywords)

            # Try major_news as additional source for keyword matching
            if len(filtered_df) < 15:
                try:
                    major_df = pro.major_news(
                        src='',
                        start_date=start_dt,
                        end_date=end_dt,
                        fields='title,content,pub_time,src'
                    )
                    if not major_df.empty:
                        major_df = major_df.rename(columns={'pub_time': 'datetime', 'src': 'data_source'})
                        major_df['data_source'] = 'major_news_' + major_df['data_source'].astype(str)
                        merged_with_major = pd.concat([merged_df, major_df], ignore_index=True)
                        merged_with_major = merged_with_major.drop_duplicates(subset=['title'], keep='first')
                        filtered_df = _filter_by_keywords(merged_with_major, keywords)
                        merged_df = merged_with_major  # Update merged_df for LLM fallback
                except Exception:
                    pass

            # Sort by datetime descending
            if 'datetime' in filtered_df.columns:
                filtered_df = filtered_df.sort_values('datetime', ascending=False)
            elif 'pub_time' in filtered_df.columns:
                filtered_df = filtered_df.sort_values('pub_time', ascending=False)

            TARGET_COUNT = 15

            if len(filtered_df) >= TARGET_COUNT:
                # Keyword filter sufficient — return top N
                final_df = filtered_df.head(TARGET_COUNT)
                header = f"# Tushare News for {ticker}\n"
                header += f"# Company name: {company_name or 'N/A'}\n"
                header += f"# Date range: {start_date} to {end_date}\n"
                header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                header += f"# Keywords used for filtering: {keywords}\n"
                header += f"# Total raw news collected: {len(merged_df)}\n"
                header += f"# Keyword-filtered results: {len(filtered_df)}\n"
                header += f"# Final results: {len(final_df)}\n"
                header += f"# Data sources: {', '.join(company_news_sources)}\n"
                return _format_to_csv(final_df, header)

            # Keyword filter insufficient — use LLM semantic supplement
            keyword_results = filtered_df.copy()

            # Build candidate pool: all news NOT already in keyword results
            excluded_indices = set(keyword_results.index)
            candidate_df = merged_df[~merged_df.index.isin(excluded_indices)].copy()

            # Sort candidates by date
            if 'datetime' in candidate_df.columns:
                candidate_df = candidate_df.sort_values('datetime', ascending=False)
            elif 'pub_time' in candidate_df.columns:
                candidate_df = candidate_df.sort_values('pub_time', ascending=False)

            need_count = TARGET_COUNT - len(keyword_results)

            if not candidate_df.empty and need_count > 0:
                selected_indices = _llm_select_relevant_news(
                    ticker=ticker,
                    company_name=company_name or ticker,
                    candidates_df=candidate_df,
                    target_count=need_count,
                )
                if selected_indices:
                    llm_supplement = candidate_df.loc[candidate_df.index.isin(selected_indices)]
                    final_df = pd.concat([keyword_results, llm_supplement], ignore_index=True)
                else:
                    final_df = keyword_results
            else:
                final_df = keyword_results

            header = f"# Tushare News for {ticker}\n"
            header += f"# Company name: {company_name or 'N/A'}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# Keywords used for filtering: {keywords}\n"
            header += f"# Total raw news collected: {len(merged_df)}\n"
            header += f"# Keyword-filtered results: {len(keyword_results)}\n"
            if len(final_df) > len(keyword_results):
                header += f"# LLM semantic supplement: {len(final_df) - len(keyword_results)}\n"
            header += f"# Final results: {len(final_df)}\n"
            header += f"# Data sources: {', '.join(company_news_sources)}\n"

            return _format_to_csv(final_df, header) + "\n_FALLBACK_TO_AKSHARE_"

        else:
            # No news from tushare, trigger akshare fallback
            header = f"# Tushare News for {ticker}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# NOTE: Tushare returned no news, falling back to akshare.\n"
            return header + "\n_FALLBACK_TO_AKSHARE_"

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare news for {ticker}: {str(e)}")


def get_global_news(
    curr_date: Annotated[str, "当前日期，格式：yyyy-mm-dd"] = None,
    look_back_days: Annotated[int, "回溯天数"] = 7,
    limit: Annotated[int, "返回的最大文章数"] = 200,
    ticker: Annotated[str, "股票代码（可选，用于行业相关性筛选）"] = None,
) -> str:
    """Get global financial news using Tushare Pro.

    Strategy:
    1. Call tushare news API with global-focused sources (wallstreetcn, yuncaijing)
    2. If ticker provided, filter by industry keywords; if insufficient, use LLM semantic filter
    3. Fallback/supplement with akshare (cls + cctv)

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of news items to return
        ticker: A-share ticker symbol (optional, for industry relevance filtering)

    Returns:
        CSV string containing global financial news
    """
    try:
        pro = _get_pro_api()

        if curr_date is None:
            curr_date = datetime.now().strftime("%Y-%m-%d")

        # Calculate date range
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=look_back_days)

        start_str = f"{start_dt.strftime('%Y-%m-%d')} 00:00:00"
        end_str = f"{end_dt.strftime('%Y-%m-%d')} 23:59:59"

        # Data sources for global/macro news (per user's specification)
        global_news_sources = ['wallstreetcn', 'yuncaijing']

        all_news = []

        for src in global_news_sources:
            try:
                df = pro.news(src=src, start_date=start_str, end_date=end_str)
                if not df.empty:
                    df['data_source'] = src
                    all_news.append(df)
            except Exception:
                continue

        if not all_news:
            # Trigger akshare fallback
            header = f"# Tushare Global Financial News\n"
            header += f"# Date range: {start_dt.strftime('%Y-%m-%d')} to {curr_date}\n"
            header += f"# NOTE: Tushare returned no news, falling back to akshare.\n"
            return header + "\n_FALLBACK_TO_AKSHARE_"

        merged_df = pd.concat(all_news, ignore_index=True)
        merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')

        # Sort by datetime descending
        if 'datetime' in merged_df.columns:
            merged_df = merged_df.sort_values('datetime', ascending=False)

        TARGET_COUNT = 10

        # If ticker provided, try keyword filtering by industry/company
        if ticker:
            company_name = _get_stock_name_from_code(ticker)
            keywords = [ticker.split('.')[0]]
            if company_name:
                keywords.append(company_name)

            filtered_df = _filter_by_keywords(merged_df, keywords)

            # Sort filtered results
            if 'datetime' in filtered_df.columns:
                filtered_df = filtered_df.sort_values('datetime', ascending=False)

            if len(filtered_df) >= TARGET_COUNT:
                # Keyword filter sufficient
                final_df = filtered_df.head(TARGET_COUNT)
                header = f"# Tushare Global Financial News\n"
                header += f"# Ticker: {ticker} | Company: {company_name or 'N/A'}\n"
                header += f"# Date range: {start_dt.strftime('%Y-%m-%d')} to {curr_date}\n"
                header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                header += f"# Total items: {len(merged_df)}\n"
                header += f"# Keyword-filtered: {len(filtered_df)} | Final: {len(final_df)}\n"
                header += f"# Data sources: {', '.join(global_news_sources)}\n"
                return _format_to_csv(final_df, header)

            # Keyword filter insufficient — use LLM semantic supplement
            keyword_results = filtered_df.copy()
            excluded_indices = set(keyword_results.index)
            candidate_df = merged_df[~merged_df.index.isin(excluded_indices)].copy()

            need_count = TARGET_COUNT - len(keyword_results)

            if not candidate_df.empty and need_count > 0:
                selected_indices = _llm_select_relevant_news(
                    ticker=ticker,
                    company_name=company_name or ticker,
                    candidates_df=candidate_df,
                    target_count=need_count,
                )
                if selected_indices:
                    llm_supplement = candidate_df.loc[candidate_df.index.isin(selected_indices)]
                    final_df = pd.concat([keyword_results, llm_supplement], ignore_index=True)
                else:
                    final_df = keyword_results
            else:
                final_df = keyword_results

            header = f"# Tushare Global Financial News\n"
            header += f"# Ticker: {ticker} | Company: {company_name or 'N/A'}\n"
            header += f"# Date range: {start_dt.strftime('%Y-%m-%d')} to {curr_date}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# Total items: {len(merged_df)}\n"
            header += f"# Keyword-filtered: {len(keyword_results)}\n"
            if len(final_df) > len(keyword_results):
                header += f"# LLM semantic supplement: {len(final_df) - len(keyword_results)}\n"
            header += f"# Final results: {len(final_df)}\n"
            header += f"# Data sources: {', '.join(global_news_sources)}\n"
            return _format_to_csv(final_df, header)

        # No ticker — return top N global news (original behavior)
        merged_df = merged_df.head(limit)

        header = f"# Tushare Global Financial News\n"
        header += f"# Date range: {start_dt.strftime('%Y-%m-%d')} to {curr_date}\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total items: {len(merged_df)}\n"
        header += f"# Data sources: {', '.join(global_news_sources)}\n"

        return _format_to_csv(merged_df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        return f"Tushare global news unavailable: {str(e)}"


def get_cctv_news(
    look_back_days: Annotated[int, "回溯天数，默认3天"] = 3,
) -> str:
    """Get CCTV news broadcast text transcripts using Tushare Pro.

    Provides official policy announcements and macro economic policy content,
    which is essential for A-share policy market analysis.

    Args:
        look_back_days: Number of days to look back (default: 3 days)

    Returns:
        CSV string containing CCTV news broadcast transcripts
    """
    try:
        pro = _get_pro_api()

        # Get news for recent days
        all_cctv = []
        today = datetime.now()

        for i in range(look_back_days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")

            try:
                df = pro.cctv_news(date=date_str)
                if not df.empty:
                    df['retrieved_date'] = date.strftime("%Y-%m-%d")
                    all_cctv.append(df)
            except Exception:
                # Some dates may not have data yet (e.g., today's broadcast not uploaded)
                continue

        if all_cctv:
            merged_df = pd.concat(all_cctv, ignore_index=True)

            header = f"# CCTV News Broadcast Transcripts (新闻联播文字稿)\n"
            header += f"# Date range: {(today - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}\n"
            header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# Total segments: {len(merged_df)}\n"
            header += f"# Note: Official policy announcements for macro analysis\n"

            return _format_to_csv(merged_df, header)

        else:
            return f"No CCTV news broadcast data available for the past {look_back_days} days"

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get CCTV news: {str(e)}")


def get_insider_transactions(
    ticker: Annotated[str, "A-share ticker symbol"],
) -> str:
    """Get insider transactions (shareholder changes) using Tushare Pro.

    Args:
        ticker: A-share ticker symbol

    Returns:
        CSV string containing insider transaction data
    """
    try:
        pro = _get_pro_api()
        ts_code = _convert_ticker_to_tushare(ticker)

        # Tushare's stk_holdertrade interface for shareholder trading changes
        df = pro.stk_holdertrade(ts_code=ts_code)

        if df.empty:
            return f"No insider transaction data found for {ticker} via Tushare"

        header = f"# Insider Transactions for {ticker} (Tushare Pro)\n"
        header += f"# Retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Total records: {len(df)}\n"

        return _format_to_csv(df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get Tushare insider transactions for {ticker}: {str(e)}")