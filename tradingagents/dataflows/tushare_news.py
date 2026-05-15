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

# Keyword cache for LLM-generated keywords
try:
    from tradingagents.utils.data_cache import get_keyword_cache
    KEYWORD_CACHE_AVAILABLE = True
except ImportError:
    KEYWORD_CACHE_AVAILABLE = False

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

COMPANY_NEWS_SOURCES = ['eastmoney', 'sina', '10jqka', 'cls', 'yicai', 'jinrongjie']
INDUSTRY_FAST_NEWS_SOURCES = ['eastmoney', 'sina', '10jqka', 'cls', 'yicai', 'jinrongjie']


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
        if header_info:
            return header_info + "\nNo data available"
        return "No data available"

    csv_string = df.to_csv(index=False)

    if header_info:
        return header_info + "\n" + csv_string

    return csv_string


def _company_keywords(ticker: str, company_name: Optional[str]) -> List[str]:
    """Build strict entity keywords for direct company news matching."""
    stock_code = _convert_ticker_to_tushare(ticker)
    code = stock_code.split('.')[0]
    keywords = [stock_code, code]
    if company_name:
        keywords.append(company_name)
        short_name = company_name
        for suffix in ["股份有限公司", "有限责任公司", "有限公司", "集团股份", "集团", "控股"]:
            short_name = short_name.replace(suffix, "")
        short_name = short_name.strip()
        if short_name and short_name != company_name:
            keywords.append(short_name)
    return list(dict.fromkeys([kw for kw in keywords if kw]))


def _filter_company_entity_news(df: pd.DataFrame, keywords: List[str]) -> pd.DataFrame:
    """Filter rows that explicitly mention the target company or stock code."""
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
            str(row.get('title', '')) + " " +
            str(row.get('content', '')) + " " +
            str(row.get('新闻标题', '')) + " " +
            str(row.get('新闻内容', ''))
        ).lower()
        if any(keyword in text for keyword in name_terms + ticker_terms):
            return True
        for code in code_terms:
            code_pattern = rf"(股票代码|证券代码|代码)[:：\s]*{code}\b|{code}\.(sh|sz)\b|(sh|sz){code}\b"
            if re.search(code_pattern, text):
                return True
        return False

    return df[df.apply(matches_row, axis=1)].copy()


def _fetch_news_source(pro, src: str, start_dt_obj: datetime, end_dt_obj: datetime) -> pd.DataFrame:
    """Fetch one Tushare news source, using segmentation for high-volume feeds."""
    if src in SEGMENTED_SOURCES["company"]:
        return _segmented_fetch(pro, src, start_dt_obj, end_dt_obj)

    start_dt = start_dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    end_dt = end_dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    df = pro.news(src=src, start_date=start_dt, end_date=end_dt)
    if not df.empty:
        df['data_source'] = src
    return df


def _annotate_industry_relation(
    df: pd.DataFrame,
    ticker: str,
    company_keywords: List[str],
    industry_keywords: List[str],
    expanded_keywords: List[str],
) -> pd.DataFrame:
    """Add deterministic relation labels for industry/supply-chain news."""
    if df.empty:
        return df

    code = ticker.split('.')[0].lower()
    company_terms = [kw.lower() for kw in company_keywords if kw]
    industry_terms = [kw.lower() for kw in industry_keywords if kw]
    expanded_terms = [kw.lower() for kw in expanded_keywords if kw]
    macro_terms = ["政策", "监管", "央行", "降准", "降息", "lpr", "利率", "社融", "m2", "融资", "信贷", "流动性", "资本市场", "金融支持"]
    upstream_terms = ["上游", "原材料", "设备", "供应", "采购", "成本", "价格"]
    downstream_terms = ["下游", "需求", "客户", "消费", "订单", "销售", "房地产", "贷款"]
    competitor_terms = ["同业", "竞争", "招商银行", "兴业银行", "平安银行", "工商银行", "建设银行", "农业银行", "中国银行"]
    technology_terms = ["技术", "数字化", "ai", "人工智能", "系统", "平台", "创新", "产品"]

    def classify(row):
        text = (
            str(row.get('title', '')) + " " +
            str(row.get('content', '')) + " " +
            str(row.get('summary', ''))
        ).lower()
        matched = [kw for kw in company_terms + industry_terms + expanded_terms if kw and kw in text]

        if any(term in text for term in company_terms) or code in text:
            relation_type = "company_direct"
            direct_or_indirect = "直接"
            impact_path = "新闻直接提及目标公司或股票代码，作为公司自身事件分析。"
        elif any(term in text for term in macro_terms):
            relation_type = "macro_policy"
            direct_or_indirect = "间接"
            impact_path = "通过宏观政策、流动性或监管环境变化传导至目标公司所在行业。"
        elif any(term in text for term in competitor_terms):
            relation_type = "competitor_dynamic"
            direct_or_indirect = "间接"
            impact_path = "通过同业竞争格局、估值锚或业务表现对目标公司形成间接影响。"
        elif any(term in text for term in upstream_terms):
            relation_type = "upstream_supply"
            direct_or_indirect = "间接"
            impact_path = "通过上游资源、资金成本、供应或价格变化影响目标公司经营条件。"
        elif any(term in text for term in downstream_terms):
            relation_type = "downstream_demand"
            direct_or_indirect = "间接"
            impact_path = "通过下游需求、客户融资或消费/投资意愿变化影响目标公司业务需求。"
        elif any(term in text for term in technology_terms):
            relation_type = "technology_trend"
            direct_or_indirect = "间接"
            impact_path = "通过行业技术、产品或数字化趋势影响目标公司中长期竞争力。"
        else:
            relation_type = "industry_trend"
            direct_or_indirect = "间接"
            impact_path = "通过行业景气、市场情绪或板块趋势对目标公司产生间接影响。"

        return pd.Series({
            "direct_or_indirect": direct_or_indirect,
            "relation_type": relation_type,
            "impact_path": impact_path,
            "matched_keywords": ",".join(list(dict.fromkeys(matched[:10]))),
        })

    annotated = df.copy()
    relation_df = annotated.apply(classify, axis=1)
    for col in relation_df.columns:
        annotated[col] = relation_df[col]
    return annotated


def _industry_data_llm_enabled() -> bool:
    """Enable expensive data-layer LLM processing only when explicitly requested."""
    return os.environ.get("TRADINGAGENTS_NEWS_DATA_LLM", "0").strip() == "1"


def _rank_industry_candidates(
    df: pd.DataFrame,
    company_keywords: List[str],
    industry_keywords: List[str],
    expanded_keywords: List[str],
) -> pd.DataFrame:
    """Rank industry candidates deterministically to avoid LLM timeout/fallback."""
    if df.empty:
        return df

    company_terms = [kw.lower() for kw in company_keywords if kw]
    industry_terms = [kw.lower() for kw in industry_keywords if kw]
    expanded_terms = [kw.lower() for kw in expanded_keywords if kw]
    macro_terms = ["政策", "监管", "央行", "降准", "降息", "lpr", "利率", "社融", "融资", "信贷", "流动性"]

    def score(row):
        text = (
            str(row.get('title', '')) + " " +
            str(row.get('content', ''))
        ).lower()
        value = 0
        value += 8 * sum(1 for kw in company_terms if kw in text)
        value += 4 * sum(1 for kw in industry_terms if kw in text)
        value += 2 * sum(1 for kw in expanded_terms if kw in text)
        value += 2 * sum(1 for kw in macro_terms if kw in text)
        content_len = len(_strip_html(str(row.get('content', ''))))
        if content_len > 100:
            value += 1
        return value

    ranked = df.copy()
    ranked['_relevance_score'] = ranked.apply(score, axis=1)
    sort_cols = ['_relevance_score']
    ascending = [False]
    if 'datetime' in ranked.columns:
        sort_cols.append('datetime')
        ascending.append(False)
    elif 'pub_time' in ranked.columns:
        sort_cols.append('pub_time')
        ascending.append(False)
    ranked = ranked.sort_values(sort_cols, ascending=ascending)
    return ranked.drop(columns=['_relevance_score'])


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
        return []

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
        return []


def _llm_expand_keywords(
    ticker: str,
    company_name: str,
    industry_context: str,
) -> List[str]:
    """Use LLM to generate expanded keywords for industry news filtering.

    Returns a list of keywords covering upstream, downstream, competitors,
    and technology/product terms related to the company.
    """
    # Check cache first (30 day TTL for LLM-generated keywords)
    if KEYWORD_CACHE_AVAILABLE:
        cache = get_keyword_cache()
        cached = cache.get_keywords(ticker)
        if cached:
            return cached

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
        keywords = keywords[:30]  # 上限30个

        # Cache the result
        if KEYWORD_CACHE_AVAILABLE and keywords:
            cache.set_keywords(ticker, keywords)

        return keywords
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
        return cctv_df.iloc[0:0].copy()
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

    调用 tushare news API（6源分段拉取）+ major_news 长篇通讯，
    通过公司名+股票代码关键词筛选，最多返回 20 条。
    """
    try:
        pro = _get_pro_api()
        stock_code = _convert_ticker_to_tushare(ticker)

        company_name = _get_stock_name_from_code(ticker)
        keywords = _company_keywords(stock_code, company_name)

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=NEW_DAYS)).strftime("%Y-%m-%d")

        start_dt = f"{start_date} 00:00:00"
        end_dt = f"{end_date} 23:59:59"

        all_news = []

        start_dt_obj = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
        end_dt_obj = datetime.strptime(end_dt, "%Y-%m-%d %H:%M:%S")

        try:
            major_df = _segmented_fetch_major(pro, start_dt_obj, end_dt_obj)
            if not major_df.empty:
                if 'content' in major_df.columns:
                    major_df['content'] = major_df['content'].apply(_strip_html)
                all_news.append(major_df)
        except Exception:
            pass

        for src in COMPANY_NEWS_SOURCES:
            try:
                df = _fetch_news_source(pro, src, start_dt_obj, end_dt_obj)
                if not df.empty:
                    all_news.append(df)
            except Exception:
                continue

        if all_news:
            merged_df = pd.concat(all_news, ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')
            filtered_df = _filter_company_entity_news(merged_df, keywords)

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
            final_df = keyword_results

            header = f"# 第一层 · 公司直接相关新闻 ({ticker})\n"
            header += f"# Company name: {company_name or 'N/A'}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# Keywords: {keywords}\n"
            header += f"# Total raw: {len(merged_df)} | Keyword hits: {len(keyword_results)}\n"
            header += f"# Final: {len(final_df)}\n"

            if len(final_df) >= 10:
                return _format_to_csv(final_df, header)
            return _format_to_csv(final_df, header) + "\n# _FALLBACK_TO_AKSHARE_"

        else:
            header = f"# 第一层 · 公司直接相关新闻 ({ticker})\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# NOTE: Tushare returned no news, falling back to akshare.\n"
            return header + "\n# _FALLBACK_TO_AKSHARE_"

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

    调用 tushare major_news（长篇通讯，12h 分段）+ news 六源快讯，
    通过行业关键词初筛、确定性排序和关系标注筛选。
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

        # 2. news 快讯池作为行业/上下游补充。这里允许其他公司新闻进入候选，
        # 但后续必须标注为间接影响，不能混作公司直接新闻。
        for src in INDUSTRY_FAST_NEWS_SOURCES:
            try:
                fast_df = _fetch_news_source(pro, src, start_dt_obj, end_dt_obj)
                if not fast_df.empty:
                    all_news.append(fast_df)
            except Exception:
                pass

        if not all_news:
            header = f"# 第二层 · 产业链/行业新闻 ({ticker})\n"
            header += f"# Industry: {industry_context}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# NOTE: Tushare returned no industry news, falling back to akshare.\n"
            return header + "\n# _FALLBACK_TO_AKSHARE_"

        merged_df = pd.concat(all_news, ignore_index=True)
        merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')

        # === 关键词扩展 + 初筛 ===
        # 1. 基础关键词：公司实体 + 行业
        company_entity_keywords = _company_keywords(ticker, company_name)
        base_keywords = company_entity_keywords.copy()
        if industry_keywords:
            base_keywords.extend(industry_keywords)

        # 2. 可选 LLM 生成扩展关键词（上下游/竞争/技术等）。
        # 默认关闭，避免数据层多次 LLM 调用导致 route_to_vendor 超时。
        if _industry_data_llm_enabled():
            expanded = _llm_expand_keywords(
                ticker=ticker,
                company_name=company_name or ticker,
                industry_context=industry_context,
            )
        else:
            expanded = []

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

        filtered_df = _rank_industry_candidates(
            filtered_df,
            company_keywords=company_entity_keywords,
            industry_keywords=industry_keywords,
            expanded_keywords=expanded,
        )

        TARGET_COUNT = 20

        if filtered_df.empty:
            header = f"# 第二层 · 产业链/行业新闻 ({ticker})\n"
            header += f"# Company: {company_name or 'N/A'} | Industry: {industry_context}\n"
            header += f"# Keywords ({len(all_keywords)}): {all_keywords[:15]}{'...' if len(all_keywords) > 15 else ''}\n"
            header += f"# Date range: {start_date} to {end_date}\n"
            header += f"# Total raw: {len(merged_df)} | Keyword filtered: 0 | Selected: 0\n"
            header += "# Final: 0 (LLM summarized)\n"
            header += "# NOTE: Tushare returned no industry-relevant news after keyword filtering, falling back to akshare.\n"
            return header + "\nNo data available\n# _FALLBACK_TO_AKSHARE_"

        # 4. 精选候选。默认用确定性评分；显式开启时使用 LLM 精选。
        if _industry_data_llm_enabled() and len(filtered_df) > TARGET_COUNT:
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
            selected_df = filtered_df.head(TARGET_COUNT).copy()

        # 可选 LLM 摘要；默认用正文截断，最终报告由新闻分析师统一归纳。
        if _industry_data_llm_enabled():
            summarized_df = _llm_summarize_news(
                articles_df=selected_df,
                ticker=ticker,
                industry_context=industry_context,
            )
            summary_mode = "LLM summarized"
        else:
            summarized_df = selected_df.copy()
            if 'content' in summarized_df.columns:
                summarized_df['summary'] = summarized_df['content'].apply(lambda x: _strip_html(str(x))[:300])
            elif 'title' in summarized_df.columns:
                summarized_df['summary'] = summarized_df['title'].apply(lambda x: _strip_html(str(x))[:300])
            else:
                summarized_df['summary'] = ""
            summary_mode = "deterministic ranked"

        summarized_df = _annotate_industry_relation(
            summarized_df,
            ticker=ticker,
            company_keywords=company_entity_keywords,
            industry_keywords=industry_keywords,
            expanded_keywords=expanded,
        )

        # 只保留需要的列：title, datetime, data_source, relation fields, summary
        output_cols = [
            'title',
            'datetime',
            'data_source',
            'direct_or_indirect',
            'relation_type',
            'impact_path',
            'matched_keywords',
            'summary',
        ]
        available_cols = [c for c in output_cols if c in summarized_df.columns]
        if not available_cols:
            available_cols = summarized_df.columns.tolist()

        final_df = summarized_df[available_cols].copy()

        header = f"# 第二层 · 产业链/行业新闻 ({ticker})\n"
        header += f"# Company: {company_name or 'N/A'} | Industry: {industry_context}\n"
        header += f"# Keywords ({len(all_keywords)}): {all_keywords[:15]}{'...' if len(all_keywords) > 15 else ''}\n"
        header += f"# Date range: {start_date} to {end_date}\n"
        header += f"# Total raw: {len(merged_df)} | Keyword filtered: {len(filtered_df)} | Selected: {len(selected_df)}\n"
        header += f"# Final: {len(final_df)} ({summary_mode})\n"

        return _format_to_csv(final_df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get industry news for {ticker}: {str(e)}")


def get_policy_news(
    ticker: Annotated[str, "A-share ticker symbol"],
    look_back_days: Annotated[int, "回溯天数，默认3天"] = NEW_DAYS,
    end_date: Annotated[str, "截止日期，格式：yyyy-mm-dd"] = None,
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

        if end_date:
            end_day = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_day = datetime.now()

        # 拉取 CCTV 新闻
        all_cctv = []

        for i in range(look_back_days):
            date = end_day - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")

            try:
                df = pro.cctv_news(date=date_str)
                if not df.empty:
                    df['retrieved_date'] = date.strftime("%Y-%m-%d")
                    all_cctv.append(df)
            except Exception:
                continue

        if not all_cctv:
            header = f"# 第三层 · 政策新闻 ({ticker})\n"
            header += f"# Date range: {(end_day - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {end_day.strftime('%Y-%m-%d')}\n"
            header += f"# No CCTV news broadcast data available for the past {look_back_days} days; falling back to akshare.\n"
            return header + "No data available\n# _FALLBACK_TO_AKSHARE_"

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
        header += f"# Date range: {(end_day - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {end_day.strftime('%Y-%m-%d')}\n"
        header += f"# Total CCTV items: {len(merged_df)} | Relevant: {len(filtered_df)}\n"

        return _format_to_csv(filtered_df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get policy news for {ticker}: {str(e)}")

# ── Backward Compatibility Functions (保留旧接口) ─────────────────────────────

def get_news(
    ticker: Annotated[str, "A-share ticker symbol (e.g., 000001.SZ, 600000.SH)"],
    start_date: Annotated[str, "开始日期，格式：yyyy-mm-dd"] = None,
    end_date: Annotated[str, "结束日期，格式：yyyy-mm-dd"] = None,
) -> str:
    """Get company-specific news (backward compatibility wrapper).
    
    Delegates to get_company_news for the new three-layer architecture.
    
    Args:
        ticker: A-share ticker symbol
        start_date: Start date (yyyy-mm-dd)
        end_date: End date (yyyy-mm-dd)
    
    Returns:
        CSV-formatted news data with company news
    """
    return get_company_news(ticker, start_date, end_date)


def get_global_news(
    curr_date: Annotated[str, "当前日期，格式：yyyy-mm-dd"] = None,
    look_back_days: Annotated[int, "回溯天数"] = 7,
    limit: Annotated[int, "返回的最大文章数"] = 200,
    ticker: Annotated[str, "股票代码（可选，用于行业相关性筛选）"] = None,
) -> str:
    """Get global financial news (backward compatibility wrapper).
    
    Delegates to get_industry_news when ticker is provided,
    otherwise returns unfiltered major_news.
    
    Args:
        curr_date: Current date (yyyy-mm-dd)
        look_back_days: Days to look back
        limit: Maximum articles to return
        ticker: Optional ticker for industry filtering
    
    Returns:
        CSV-formatted news data
    """
    if ticker:
        # Use new industry news layer
        if curr_date:
            end_date = curr_date
            start_date = (datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
        return get_industry_news(ticker, start_date, end_date)
    
    # No ticker: return raw major_news (deprecated behavior)
    try:
        pro = _get_pro_api()
        if curr_date:
            end = curr_date
            start = (datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
        else:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
        
        df = pro.major_news(start_date=start, end_date=end)
        if df.empty:
            return "# No global news found\n"
        
        df = df.head(limit)
        header = f"# Global Financial News\n# Date: {start} to {end}\n# Total: {len(df)} items\n"
        return _format_to_csv(df, header)
    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get global news: {str(e)}")


def get_cctv_news(
    look_back_days: Annotated[int, "回溯天数，默认3天"] = 3,
) -> str:
    """Get CCTV news broadcast transcripts (backward compatibility wrapper).

    Returns unfiltered CCTV news without LLM filtering.
    Use get_policy_news for ticker-specific policy filtering.

    Args:
        look_back_days: Days to look back (default 3)

    Returns:
        CSV-formatted CCTV news data
    """
    try:
        pro = _get_pro_api()
        today = datetime.now()

        dfs = []
        for i in range(look_back_days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            try:
                df = pro.cctv_news(date=date)
                if not df.empty:
                    dfs.append(df)
            except Exception:
                pass

        if not dfs:
            return "# No CCTV news found\n"

        merged_df = pd.concat(dfs, ignore_index=True)
        merged_df = merged_df.sort_values('pub_time', ascending=False).reset_index(drop=True)

        header = f"# CCTV News Broadcast\n# Date: {(today - timedelta(days=look_back_days-1)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}\n# Total: {len(merged_df)} items\n"
        return _format_to_csv(merged_df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get CCTV news: {str(e)}")


# ── Recommendation System News (推荐系统专用) ────────────────────────────────

# 推荐系统数据源配置（扩展更多高质量源）
RECOMMENDATION_SOURCES = {
    # 快讯源（高频热点，6小时分段）
    "flash": ["cls", "sina", "eastmoney", "10jqka"],
    # 深度源（长篇分析，12小时分段）
    "depth": [],  # major_news已单独处理
    # 财经门户（需要分段）
    "portal": ["jinrongjie", "yicai"],
    # 全球财经（华尔街见闻）
    "global": ["wallstreetcn"],
}


def get_recommendation_news(
    look_back_days: Annotated[int, "回溯天数，每日推荐默认1天，每周推荐默认7天"] = 1,
    max_articles: Annotated[int, "返回的最大新闻数量，默认1000条（充分利用1M上下文）"] = 1000,
    include_cctv: Annotated[bool, "是否包含新闻联播政策新闻"] = True,
) -> str:
    """获取推荐系统所需的全球热点新闻（不基于特定ticker）。

    聚合多个数据源（充分利用1M上下文LLM）：
    1. 快讯源（cls/sina/eastmoney/10jqka）：实时市场热点，6小时分段
    2. 财经门户（jinrongjie/yicai）：财经资讯，单次拉取
    3. major_news（长篇通讯）：深度产业分析，12小时分段
    4. wallstreetcn（华尔街见闻）：全球财经，6小时分段
    5. cctv_news（新闻联播）：政策热点，按天拉取（可选）

    这是推荐系统ThemeExtractor的数据源，用于提取投资主题。
    与三层新闻架构的区别：
    - 不基于特定ticker，直接返回全局新闻
    - 不做关键词过滤或LLM语义筛选
    - 复用已有的分段获取逻辑，避免1500条上限
    - 支持大上下文LLM（max_articles可设300-500+）

    Args:
        look_back_days: 回溯天数（每日推荐=1，每周推荐=7）
        max_articles: 返回的最大新闻数量（默认300，可设500+）
        include_cctv: 是否包含新闻联播政策新闻

    Returns:
        CSV格式的新闻数据，包含title, content, datetime, data_source列
    """
    try:
        pro = _get_pro_api()
        today = datetime.now()
        start_date = today - timedelta(days=look_back_days)
        start_dt_obj = start_date
        end_dt_obj = today
        start_dt_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_dt_str = today.strftime("%Y-%m-%d %H:%M:%S")

        all_news = []

        # 1. 快讯源（高频热点）- 6小时分段
        for src in RECOMMENDATION_SOURCES["flash"]:
            try:
                df = _segmented_fetch(pro, src, start_dt_obj, end_dt_obj)
                if not df.empty:
                    df['data_source'] = src
                    all_news.append(df)
                    print(f"  {src}: {len(df)}条")
            except Exception as e:
                print(f"  {src}: 获取失败 ({e})")
                pass

        # 2. 财经门户 - 单次拉取（数据量较小）
        for src in RECOMMENDATION_SOURCES["portal"]:
            try:
                df = pro.news(src=src, start_date=start_dt_str, end_date=end_dt_str)
                if not df.empty:
                    df['data_source'] = src
                    all_news.append(df)
                    print(f"  {src}: {len(df)}条")
            except Exception:
                pass

        # 3. wallstreetcn（全球财经）- 6小时分段
        for src in RECOMMENDATION_SOURCES["global"]:
            try:
                df = _segmented_fetch(pro, src, start_dt_obj, end_dt_obj)
                if not df.empty:
                    df['data_source'] = src
                    all_news.append(df)
                    print(f"  {src}: {len(df)}条")
            except Exception:
                pass

        # 4. major_news（深度产业分析）- 12小时分段
        try:
            major_df = _segmented_fetch_major(pro, start_dt_obj, end_dt_obj)
            if not major_df.empty:
                all_news.append(major_df)
                print(f"  major_news: {len(major_df)}条")
        except Exception:
            pass

        # 5. cctv_news（政策热点）- 按天拉取（可选）
        if include_cctv:
            try:
                cctv_list = []
                for i in range(look_back_days):
                    date = today - timedelta(days=i)
                    date_str = date.strftime("%Y%m%d")
                    try:
                        df = pro.cctv_news(date=date_str)
                        if not df.empty:
                            df['datetime'] = df.get('pub_time', '')
                            df['data_source'] = 'cctv'
                            cctv_list.append(df)
                    except Exception:
                        continue

                if cctv_list:
                    cctv_df = pd.concat(cctv_list, ignore_index=True)
                    all_news.append(cctv_df)
                    print(f"  cctv: {len(cctv_df)}条")
            except Exception:
                pass

        if not all_news:
            return f"# 推荐系统热点新闻\n# No news available for the past {look_back_days} days\n"

        # 合并、去重、排序
        merged_df = pd.concat(all_news, ignore_index=True)
        print(f"合并总数: {len(merged_df)}条")
        merged_df = merged_df.drop_duplicates(subset=['title'], keep='first')
        print(f"去重后: {len(merged_df)}条")

        # 统一datetime列名
        if 'datetime' not in merged_df.columns and 'pub_time' in merged_df.columns:
            merged_df['datetime'] = merged_df['pub_time']

        # 按时间排序（最新在前）
        if 'datetime' in merged_df.columns:
            merged_df = merged_df.sort_values('datetime', ascending=False)

        # 清理content（去除HTML，保留完整内容供后续使用）
        if 'content' in merged_df.columns:
            merged_df['content'] = merged_df['content'].apply(
                lambda x: _strip_html(str(x))[:500] if x else ''  # 截断到500字符，平衡信息量和token消耗
            )

        # 限制返回数量
        final_df = merged_df.head(max_articles)

        # 统计各源数据量
        source_counts = final_df['data_source'].value_counts().to_dict()
        source_str = ', '.join([f"{k}:{v}" for k, v in source_counts.items()])

        header = f"# 推荐系统热点新闻\n"
        header += f"# Date range: {start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}\n"
        header += f"# Sources: {source_str}\n"
        header += f"# Total raw: {len(merged_df)} | Final: {len(final_df)} articles\n"
        header += f"# Note: Global hot news for theme extraction (no ticker filtering)\n"

        # 只保留必要列
        output_cols = ['title', 'content', 'datetime', 'data_source']
        available_cols = [c for c in output_cols if c in final_df.columns]
        if available_cols:
            final_df = final_df[available_cols]

        return _format_to_csv(final_df, header)

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get recommendation news: {str(e)}")

    except TushareDataError as e:
        raise e
    except Exception as e:
        raise TushareDataError(f"Failed to get recommendation news: {str(e)}")
