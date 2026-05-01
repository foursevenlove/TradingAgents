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
from typing import Annotated, Optional, List, Dict, Any
import pandas as pd

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

# Industry classification for keyword expansion
try:
    from tradingagents.market_data.industry_classification import get_sw_industry
    INDUSTRY_AVAILABLE = True
except ImportError:
    INDUSTRY_AVAILABLE = False

def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not text:
        return ''
    clean = re.sub(r'<[^>]+>', '', str(text))
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


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
            provider = settings.get("provider", "alibaba")
            model = settings.get("quick_think_llm", "deepseek-v4-flash")
            client = create_llm_client(provider, model)
            _FILTER_LLM = client.get_llm()
        except Exception:
            _FILTER_LLM = None
    return _FILTER_LLM


# 需要分段调用的数据源（单次1500条上限，测试显示3天内触顶的源都需要分段）
SEGMENTED_SOURCES = {
    "company": ["sina", "eastmoney", "10jqka", "cls", "jinrongjie"],
    "global": ["wallstreetcn"],
}

# 分段时间间隔（小时）
SEGMENT_HOURS = 6

# major_news 分段间隔（小时）— major_news 数据量低于 news 快讯，用更宽间隔减少 API 调用
INDUSTRY_SEGMENT_HOURS = 12

NEW_DAYS = 3


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


def _segmented_fetch(pro, src: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """分段获取新闻数据，避免1500条上限限制。

    对于高频数据源（如sina），按SEGMENT_HOURS小时分段循环调用，
    累积所有数据返回。

    Args:
        pro: Tushare Pro API实例
        src: 数据源标识
        start_date: 开始日期时间
        end_date: 结束日期时间

    Returns:
        累积的新闻DataFrame
    """
    all_news = []
    current = start_date

    while current < end_date:
        # 计算下一个分段点
        segment_end = min(
            current + timedelta(hours=SEGMENT_HOURS),
            end_date
        )

        segment_start_str = current.strftime("%Y-%m-%d %H:%M:%S")
        segment_end_str = segment_end.strftime("%Y-%m-%d %H:%M:%S")

        try:
            df = pro.news(src=src, start_date=segment_start_str, end_date=segment_end_str)
            if not df.empty:
                df['data_source'] = src
                all_news.append(df)
        except Exception:
            pass  # 某些分段可能暂时不可用，继续下一个

        current = segment_end

    if all_news:
        return pd.concat(all_news, ignore_index=True)
    return pd.DataFrame()


def _segmented_fetch_major(pro, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """分段获取 major_news 数据，避免单次上限限制。

    逻辑同 _segmented_fetch，但调用 pro.major_news() 而非 pro.news()。
    """
    all_news = []
    current = start_date

    while current < end_date:
        segment_end = min(
            current + timedelta(hours=INDUSTRY_SEGMENT_HOURS),
            end_date
        )
        segment_start_str = current.strftime("%Y-%m-%d %H:%M:%S")
        segment_end_str = segment_end.strftime("%Y-%m-%d %H:%M:%S")

        try:
            df = pro.major_news(
                src='',
                start_date=segment_start_str,
                end_date=segment_end_str,
                fields='title,content,pub_time,src'
            )
            if not df.empty:
                df = df.rename(columns={'pub_time': 'datetime', 'src': 'data_source'})
                df['data_source'] = 'major_news_' + df['data_source'].astype(str)
                all_news.append(df)
        except Exception:
            pass

        current = segment_end

    if all_news:
        return pd.concat(all_news, ignore_index=True)
    return pd.DataFrame()


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
        content = _strip_html(str(row.get('content', ''))).lower()

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
    candidate_rows = candidates_df.head(200)
    lines = []
    index_map = {}  # Maps display number -> original DataFrame index
    for display_num, (orig_idx, row) in enumerate(candidate_rows.iterrows(), 1):
        index_map[display_num] = orig_idx
        title = str(row.get('title', ''))[:120]
        date = str(row.get('datetime', row.get('pub_time', '')))[:19]
        source = str(row.get('data_source', ''))
        content = _strip_html(str(row.get('content', '')))[:500]
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


def _llm_expand_keywords(
    ticker: str,
    company_name: str,
    industry_context: str,
) -> List[str]:
    """Use LLM to generate expanded keywords for industry news filtering.

    Returns a list of keywords covering upstream, downstream, competitors,
    and technology/product terms related to the company.
    """
    llm = _get_filter_llm()
    if llm is None:
        return []

    prompt = f"""请为以下A股公司生成一组新闻筛选关键词。

公司：{company_name}({ticker})
行业：{industry_context}

请从以下5个维度各生成3-5个关键词（共15-25个）：
1. 上游产业链：核心原材料、设备、零部件相关关键词
2. 下游产业链：主要客户、应用领域相关关键词
3. 竞争对手：同行业主要可比公司名称或简称
4. 技术/产品：公司核心技术、主打产品、工艺类型相关关键词
5. 宏观关联：与公司业务强相关的宏观概念、政策热点

要求：
- 关键词要简洁（2-6个字），便于在新闻标题/正文中匹配
- 避免生僻词或只在财报中出现的专业术语
- 不要包含公司全名（已有单独筛选）

只返回关键词列表，每行一个，不要序号、不要解释、不要空行。
"""

    try:
        result = llm.invoke(prompt)
        raw = result.content if hasattr(result, 'content') else str(result)
        keywords = []
        for line in raw.split('\n'):
            kw = line.strip()
            # 去除可能的序号前缀如 "1. " 或 "- "
            kw = re.sub(r'^[\d\-\*•]+[\.\)\s]*', '', kw)
            if kw and len(kw) >= 2 and len(kw) <= 20:
                keywords.append(kw)
        return keywords[:30]  # 上限30个
    except Exception:
        return []


def _select_single_batch(
    llm,
    ticker: str,
    company_name: str,
    industry_context: str,
    batch_df: pd.DataFrame,
    pick_count: int,
    content_limit: int = 100,
) -> List[int]:
    """对单批数据调用 LLM 选择最相关的新闻。

    返回选中行的原始 DataFrame index 列表。
    """
    if batch_df.empty or pick_count <= 0:
        return []

    lines = []
    index_map = {}
    for display_num, (orig_idx, row) in enumerate(batch_df.iterrows(), 1):
        index_map[display_num] = orig_idx
        title = str(row.get('title', ''))[:120]
        date = str(row.get('datetime', row.get('pub_time', '')))[:19]
        source = str(row.get('data_source', ''))
        content = _strip_html(str(row.get('content', '')))[:content_limit]
        lines.append(
            f"{display_num}. [{date}] 来源:{source}\n"
            f"   标题:{title}\n"
            f"   摘要:{content}"
        )

    candidate_text = "\n\n".join(lines)

    prompt = f"""从以下新闻候选列表中，选出与【{company_name}({ticker})】最相关的{pick_count}条新闻。

该公司所属行业：{industry_context}

相关性判断标准（按优先级）：
1. 直接提到公司名或股票代码 → 最优先保留
2. 提到该公司的上下游产业链（供应商、客户、合作伙伴）→ 优先保留
3. 提到该公司的主要竞争对手或同行业可比公司 → 优先保留
4. 提到公司所在行业的重大趋势、技术变革、政策变化 → 可考虑保留
5. 宏观政策对该公司所在行业有直接影响 → 弱相关，仅在没有更相关新闻时保留
6. 与该公司或所在行业明显无关的新闻 → 排除

只返回编号列表，格式如：1,3,7,12,15
不要添加任何解释或额外文字。

候选新闻：
{candidate_text}
"""

    try:
        result = llm.invoke(prompt)
        raw = result.content if hasattr(result, 'content') else str(result)
        numbers = re.findall(r'\d+', raw)
        selected = []
        seen = set()
        for n_str in numbers:
            n = int(n_str)
            if n in index_map and n not in seen:
                seen.add(n)
                selected.append(index_map[n])
        return selected[:pick_count]
    except Exception:
        return batch_df.head(pick_count).index.tolist()


def _llm_select_industry_news(
    ticker: str,
    company_name: str,
    industry_context: str,
    candidates_df: pd.DataFrame,
    target_count: int,
) -> List[int]:
    """Use LLM to select industry/supply-chain relevant news from candidates.

    支持分批处理：当数据量超过 BATCH_SIZE 时，分多批调用 LLM，
    每批选出若干条，合并后再做最终筛选，确保覆盖更多数据。
    """
    if candidates_df.empty or target_count <= 0:
        return []

    llm = _get_filter_llm()
    if llm is None:
        return candidates_df.head(target_count).index.tolist()

    BATCH_SIZE = 400      # 每批处理条数（控制单批 token 量）
    PICK_PER_BATCH = 5    # 每批选出条数
    MAX_TOTAL = 3000      # 最多处理的总条数（控制 LLM 调用次数）
    DIRECT_LIMIT = 800    # 小于此数量直接一次处理，不分批

    total = len(candidates_df)
    if total > MAX_TOTAL:
        candidates_df = candidates_df.head(MAX_TOTAL)
        total = MAX_TOTAL

    # 数据量已较小（如经过关键词初筛后），直接一次处理
    if total <= DIRECT_LIMIT:
        return _select_single_batch(
            llm, ticker, company_name, industry_context,
            candidates_df, target_count, content_limit=200,
        )

    # 数据量大，分批处理
    all_picked = []
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(num_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        batch_df = candidates_df.iloc[start:end]

        picked = _select_single_batch(
            llm, ticker, company_name, industry_context,
            batch_df, PICK_PER_BATCH, content_limit=100,
        )
        all_picked.extend(picked)

    # 合并后若超过 target_count，做最终筛选
    if len(all_picked) > target_count:
        final_df = candidates_df.loc[candidates_df.index.isin(all_picked)]
        final_picked = _select_single_batch(
            llm, ticker, company_name, industry_context,
            final_df, target_count, content_limit=200,
        )
        return final_picked

    return all_picked


def _llm_summarize_news(
    articles_df: pd.DataFrame,
    ticker: str,
    industry_context: str,
) -> pd.DataFrame:
    """Use LLM to generate 200-300 character Chinese summaries for each article.

    Returns the input DataFrame with an added 'summary' column.
    If LLM fails, falls back to truncating content to 300 chars.
    """
    if articles_df.empty:
        return articles_df

    llm = _get_filter_llm()
    if llm is None:
        # Fallback: truncate content
        df = articles_df.copy()
        df['summary'] = df['content'].apply(lambda x: _strip_html(str(x))[:300])
        return df

    lines = []
    for idx, row in articles_df.iterrows():
        title = str(row.get('title', ''))[:120]
        content = _strip_html(str(row.get('content', '')))[:2000]
        lines.append(f"{idx}. 标题:{title}\n   正文:{content}")

    articles_text = "\n\n".join(lines)

    prompt = f"""对以下新闻列表中的每条新闻，撰写 200-300 字的中文摘要。

目标股票：{ticker}
所属行业：{industry_context}

摘要要求：
- 聚焦与该股票/行业的相关性（产业链上下游、竞争格局、技术趋势等）
- 提取新闻中的关键事实、数据和影响
- 每条约 200-300 字，不超过 300 字
- 按原文编号顺序返回

返回格式（严格按编号顺序）：
0. [摘要内容]
1. [摘要内容]
...

新闻列表：
{articles_text}
"""

    try:
        result = llm.invoke(prompt)
        raw = result.content if hasattr(result, 'content') else str(result)

        # Parse summaries by index
        summaries = {}
        for line in raw.split('\n'):
            match = re.match(r'^(\d+)\.\s*(.+)', line.strip())
            if match:
                idx_str, summary = match.groups()
                try:
                    idx = int(idx_str)
                    summaries[idx] = summary.strip()
                except ValueError:
                    pass

        df = articles_df.copy()
        df['summary'] = df.index.map(lambda i: summaries.get(i, _strip_html(str(df.loc[i, 'content']))[:300]))
        return df
    except Exception:
        df = articles_df.copy()
        df['summary'] = df['content'].apply(lambda x: _strip_html(str(x))[:300])
        return df


def _llm_filter_policy_news(
    cctv_df: pd.DataFrame,
    ticker: str,
    industry_info: Dict[str, Any],
) -> pd.DataFrame:
    """Use LLM to filter CCTV news for policy items relevant to the stock's industry.

    Returns a filtered DataFrame containing only relevant policy items.
    If LLM fails, returns the original DataFrame.
    """
    if cctv_df.empty:
        return cctv_df

    llm = _get_filter_llm()
    if llm is None:
        return cctv_df

    company_name = industry_info.get('company_name', ticker)
    level_1 = industry_info.get('level_1', '')
    level_2 = industry_info.get('level_2', '')

    lines = []
    index_map = {}
    for display_num, (orig_idx, row) in enumerate(cctv_df.iterrows(), 1):
        index_map[display_num] = orig_idx
        title = str(row.get('title', ''))[:200]
        content = _strip_html(str(row.get('content', '')))[:300]
        lines.append(f"{display_num}. 标题:{title}\n   内容:{content}")

    candidate_text = "\n\n".join(lines)

    prompt = f"""从以下新闻联播文字稿列表中，选出与【{company_name}({ticker})】所在行业相关的政策条目。

该公司所属行业：{level_1} / {level_2}

相关性判断标准：
1. 直接涉及该行业的产业政策、监管政策、扶持政策 → 保留
2. 涉及该行业上下游产业链的宏观政策 → 保留
3. 涉及科技创新、资本市场改革对该行业有影响的政策 → 保留
4. 纯外交、民生、体育、文化等与该行业无关 → 排除
5. 地方性政策（非全国性）且与行业无关 → 排除

只返回编号列表，格式如：1,3,7,12,15
不要添加任何解释或额外文字。

新闻联播条目：
{candidate_text}
"""

    try:
        result = llm.invoke(prompt)
        content = result.content if hasattr(result, 'content') else str(result)
        numbers = re.findall(r'\d+', content)
        selected = []
        seen = set()
        for n_str in numbers:
            n = int(n_str)
            if n in index_map and n not in seen:
                seen.add(n)
                selected.append(index_map[n])

        if selected:
            return cctv_df.loc[cctv_df.index.isin(selected)]
        return cctv_df
    except Exception:
        return cctv_df

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


def get_company_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """第一层：获取公司直接相关新闻。

    调用 tushare news API（6源分段拉取）+ akshare stock_news_em，
    通过公司名+股票代码关键词筛选，最多返回 20 条。
    """
    try:
        pro = _get_pro_api()
        stock_code = _convert_ticker_to_tushare(ticker)

        company_name = _get_stock_name_from_code(ticker)
        keywords = [stock_code.split('.')[0]]
        if company_name:
            keywords.append(company_name)

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=NEW_DAYS)).strftime("%Y-%m-%d")

        start_dt = f"{start_date} 00:00:00"
        end_dt = f"{end_date} 23:59:59"

        company_news_sources = ['eastmoney', 'sina', '10jqka', 'cls', 'yicai', 'jinrongjie']
        all_news = []

        start_dt_obj = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
        end_dt_obj = datetime.strptime(end_dt, "%Y-%m-%d %H:%M:%S")

        for src in company_news_sources:
            try:
                if src in SEGMENTED_SOURCES["company"]:
                    df = _segmented_fetch(pro, src, start_dt_obj, end_dt_obj)
                else:
                    df = pro.news(src=src, start_date=start_dt, end_date=end_dt)
                    if not df.empty:
                        df['data_source'] = src
                if not df.empty:
                    all_news.append(df)
            except Exception:
                continue

        if all_news:
            merged_df = pd.concat(all_news, ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')
            filtered_df = _filter_by_keywords(merged_df, keywords)

            if 'datetime' in filtered_df.columns:
                filtered_df = filtered_df.sort_values('datetime', ascending=False)
            elif 'pub_time' in filtered_df.columns:
                filtered_df = filtered_df.sort_values('pub_time', ascending=False)

            TARGET_COUNT = 20

            if len(filtered_df) >= TARGET_COUNT:
                final_df = filtered_df.head(TARGET_COUNT)
                header = f"# 第一层 · 公司直接相关新闻 ({ticker})\n"
                header += f"# Company name: {company_name or 'N/A'}\n"
                header += f"# Date range: {start_date} to {end_date}\n"
                header += f"# Keywords: {keywords}\n"
                header += f"# Total raw: {len(merged_df)} | Filtered: {len(filtered_df)} | Final: {len(final_df)}\n"
                return _format_to_csv(final_df, header)

            keyword_results = filtered_df.copy()
            excluded_indices = set(keyword_results.index)
            candidate_df = merged_df[~merged_df.index.isin(excluded_indices)].copy()

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

            header = f"# 第一层 · 公司直接相关新闻 ({ticker})\n"
            header += f"# Company name: {company_name or 'N/A'}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# Keywords: {keywords}\n"
            header += f"# Total raw: {len(merged_df)} | Keyword hits: {len(keyword_results)}\n"
            if len(final_df) > len(keyword_results):
                header += f"# LLM supplement: {len(final_df) - len(keyword_results)}\n"
            header += f"# Final: {len(final_df)}\n"

            if len(final_df) >= TARGET_COUNT:
                return _format_to_csv(final_df, header)
            return _format_to_csv(final_df, header) + "\n_FALLBACK_TO_AKSHARE_"

        else:
            header = f"# 第一层 · 公司直接相关新闻 ({ticker})\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# NOTE: Tushare returned no news, falling back to akshare.\n"
            return header + "\n_FALLBACK_TO_AKSHARE_"

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get company news for {ticker}: {str(e)}")


def get_industry_news(
    ticker: Annotated[str, "A-share ticker symbol"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """第二层：获取产业链/行业间接相关新闻。

    调用 tushare major_news（长篇通讯，12h 分段）+ akshare 财联社，
    通过行业关键词初筛 → LLM 精选 20 条 → LLM 生成 200-300 字摘要。
    """
    try:
        pro = _get_pro_api()

        # 获取行业分类
        industry_info = {}
        if INDUSTRY_AVAILABLE:
            try:
                industry_info = get_sw_industry(ticker) or {}
            except Exception:
                pass

        company_name = industry_info.get('company_name') or _get_stock_name_from_code(ticker)
        level_1 = industry_info.get('level_1', '')
        level_2 = industry_info.get('level_2', '')
        level_3 = industry_info.get('level_3', '')

        industry_keywords = [kw for kw in [level_1, level_2, level_3] if kw and kw != '未知']
        industry_context = ' / '.join(industry_keywords) if industry_keywords else '未知行业'

        # 日期范围
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=NEW_DAYS)).strftime("%Y-%m-%d")

        start_dt = f"{start_date} 00:00:00"
        end_dt = f"{end_date} 23:59:59"
        start_dt_obj = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
        end_dt_obj = datetime.strptime(end_dt, "%Y-%m-%d %H:%M:%S")

        all_news = []

        # 1. major_news（长篇通讯）
        try:
            major_df = _segmented_fetch_major(pro, start_dt_obj, end_dt_obj)
            if not major_df.empty:
                if 'content' in major_df.columns:
                    major_df['content'] = major_df['content'].apply(_strip_html)
                all_news.append(major_df)
        except Exception:
            pass

        # 2. 财联社快讯（cls）作为补充
        try:
            cls_df = pro.news(src='cls', start_date=start_dt, end_date=end_dt)
            if not cls_df.empty:
                cls_df['data_source'] = 'cls'
                all_news.append(cls_df)
        except Exception:
            pass

        if not all_news:
            header = f"# 第二层 · 产业链/行业新闻 ({ticker})\n"
            header += f"# Industry: {industry_context}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# NOTE: Tushare returned no industry news, falling back to akshare.\n"
            return header + "\n_FALLBACK_TO_AKSHARE_"

        merged_df = pd.concat(all_news, ignore_index=True)
        merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')

        # === 关键词扩展 + 初筛 ===
        # 1. 基础关键词：公司名 + 股票代码 + 行业
        code = ticker.split('.')[0]
        base_keywords = [code]
        if company_name:
            base_keywords.append(company_name)
        if industry_keywords:
            base_keywords.extend(industry_keywords)

        # 2. LLM 生成扩展关键词（上下游/竞争/技术等）
        expanded = _llm_expand_keywords(
            ticker=ticker,
            company_name=company_name or ticker,
            industry_context=industry_context,
        )

        all_keywords = list(dict.fromkeys(base_keywords + expanded))  # 去重保持顺序

        # 3. 关键词初筛
        if all_keywords:
            filtered_df = _filter_by_keywords(merged_df, all_keywords)
        else:
            filtered_df = merged_df.copy()

        if 'datetime' in filtered_df.columns:
            filtered_df = filtered_df.sort_values('datetime', ascending=False)
        elif 'pub_time' in filtered_df.columns:
            filtered_df = filtered_df.sort_values('pub_time', ascending=False)

        TARGET_COUNT = 20

        # 4. LLM 精选
        if len(filtered_df) > TARGET_COUNT:
            selected_indices = _llm_select_industry_news(
                ticker=ticker,
                company_name=company_name or ticker,
                industry_context=industry_context,
                candidates_df=filtered_df,
                target_count=TARGET_COUNT,
            )
            if selected_indices:
                selected_df = filtered_df.loc[filtered_df.index.isin(selected_indices)]
            else:
                selected_df = filtered_df.head(TARGET_COUNT)
        else:
            selected_df = filtered_df.copy()

        # LLM 生成摘要
        summarized_df = _llm_summarize_news(
            articles_df=selected_df,
            ticker=ticker,
            industry_context=industry_context,
        )

        # 只保留需要的列：title, datetime, data_source, summary
        output_cols = ['title', 'datetime', 'data_source', 'summary']
        available_cols = [c for c in output_cols if c in summarized_df.columns]
        if not available_cols:
            available_cols = summarized_df.columns.tolist()

        final_df = summarized_df[available_cols].copy()

        header = f"# 第二层 · 产业链/行业新闻 ({ticker})\n"
        header += f"# Company: {company_name or 'N/A'} | Industry: {industry_context}\n"
        header += f"# Keywords ({len(all_keywords)}): {all_keywords[:15]}{'...' if len(all_keywords) > 15 else ''}\n"
        header += f"# Date range: {start_date} to {end_date}\n"
        header += f"# Total raw: {len(merged_df)} | Keyword filtered: {len(filtered_df)} | Selected: {len(selected_df)}\n"
        header += f"# Final: {len(final_df)} (LLM summarized)\n"

        return _format_to_csv(final_df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get industry news for {ticker}: {str(e)}")


def get_policy_news(
    ticker: Annotated[str, "A-share ticker symbol"],
    look_back_days: Annotated[int, "回溯天数，默认3天"] = NEW_DAYS,
) -> str:
    """第三层：获取政策/宏观新闻。

    调用 tushare cctv_news API，拉取新闻联播文字稿，
    通过 LLM 筛选与目标股票行业相关的政策条目。
    """
    try:
        pro = _get_pro_api()

        # 获取行业分类
        industry_info = {}
        if INDUSTRY_AVAILABLE:
            try:
                industry_info = get_sw_industry(ticker) or {}
            except Exception:
                pass

        company_name = industry_info.get('company_name') or _get_stock_name_from_code(ticker)
        level_1 = industry_info.get('level_1', '')
        level_2 = industry_info.get('level_2', '')
        industry_context = ' / '.join([w for w in [level_1, level_2] if w and w != '未知'])

        # 拉取 CCTV 新闻
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
                continue

        if not all_cctv:
            return f"# 第三层 · 政策新闻 ({ticker})\n# No CCTV news broadcast data available for the past {look_back_days} days\n"

        merged_df = pd.concat(all_cctv, ignore_index=True)

        # LLM 筛选行业相关政策
        filtered_df = _llm_filter_policy_news(
            cctv_df=merged_df,
            ticker=ticker,
            industry_info={
                'company_name': company_name or ticker,
                'level_1': level_1,
                'level_2': level_2,
            },
        )

        header = f"# 第三层 · 政策新闻 ({ticker})\n"
        header += f"# Company: {company_name or 'N/A'} | Industry: {industry_context or 'N/A'}\n"
        header += f"# Date range: {(today - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}\n"
        header += f"# Total CCTV items: {len(merged_df)} | Relevant: {len(filtered_df)}\n"

        return _format_to_csv(filtered_df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get policy news for {ticker}: {str(e)}")