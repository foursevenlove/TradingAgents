"""Theme Extractor - Extract investment themes from cached news data.

Optimized version: Uses cached structured data instead of raw news API.

Key improvements:
- Reads from NewsCacheManager (three-layer storage)
- Uses structured info (key_entities, keywords, importance)
- Integrates ThemeTracker for continuity
- Faster and more accurate theme extraction
"""

import json
import logging
import re
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from tradingagents.llm_clients import create_llm_client
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.recommendation.news_cache_manager import get_cache_manager
from tradingagents.recommendation.news_parsing import parse_recommendation_news_csv
from tradingagents.recommendation.theme_tracker import ThemeTracker


logger = logging.getLogger("tradingagents.web.recommendation.theme_extractor")


class ThemeExtractor:
    """Extract investment themes from cached news using LLM."""

    def __init__(self, config: Dict = None):
        self.config = config or DEFAULT_CONFIG
        self.cache_manager = get_cache_manager()
        self.theme_tracker = ThemeTracker()

        # Use quick_think LLM for theme extraction
        client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
        )
        self.llm = client.get_llm()

    # ── Cached Data Extraction (Primary Method) ─────────────────────────────

    def get_cached_news_for_extraction(
        self,
        look_back_days: int = 1,
        min_importance: float = 0.3,
        as_of_date: Optional[str] = None,
    ) -> List[Dict]:
        """Get processed news from cache for theme extraction.

        Args:
            look_back_days: Days to look back (daily=1, weekly=7)
            min_importance: Minimum importance threshold

        Returns:
            List of news with structured info
        """
        end_dt = self._parse_date(as_of_date)
        look_back_days = max(1, look_back_days)
        start_date = (end_dt - timedelta(days=look_back_days - 1)).strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

        return self.cache_manager.get_news_for_theme_extraction(
            start_date=start_date,
            end_date=end_date,
            min_importance=min_importance,
        )

    def _parse_date(self, value: Optional[str]) -> datetime:
        if not value:
            return datetime.now()
        return datetime.strptime(value[:10], "%Y-%m-%d")

    def extract_themes_from_cache(
        self,
        look_back_days: int = 1,
        max_themes: int = 5,
        min_importance: float = 0.3,
        with_tracking: bool = True,
        as_of_date: Optional[str] = None,
    ) -> List[Dict]:
        """Extract themes from cached structured data.

        This is the PRIMARY method now - uses cache instead of API.

        Args:
            look_back_days: Days to look back (daily=1, weekly=7)
            max_themes: Maximum themes to extract
            min_importance: Minimum importance for news
            with_tracking: Whether to add continuity tracking

        Returns:
            List of theme dicts with continuity info
        """
        # 1. Get cached news with structured info
        news_list = self.get_cached_news_for_extraction(
            look_back_days,
            min_importance,
            as_of_date=as_of_date,
        )

        if not news_list:
            logger.warning(
                "No cached news available, falling back to recommendation news API",
                extra={"extra_data": {
                    "stage": "theme_extract_cache_empty",
                    "look_back_days": look_back_days,
                    "min_importance": min_importance,
                    "as_of_date": as_of_date,
                }},
            )
            return self.extract_themes_from_api(
                look_back_days,
                max_themes,
                as_of_date=as_of_date,
            )

        logger.info(
            "Using cached news for theme extraction",
            extra={"extra_data": {
                "stage": "theme_extract_cache",
                "news_count": len(news_list),
                "look_back_days": look_back_days,
            }},
        )

        # 2. Aggregate structured data for LLM
        aggregated = self._aggregate_structured_data(news_list)

        # 3. Extract themes using LLM
        themes = self._extract_themes_from_structured(aggregated, max_themes)

        # 4. Add news_count to each theme
        for theme in themes:
            theme["news_count"] = self._count_related_news(theme, news_list)

        # 5. Track themes for continuity (if enabled)
        if with_tracking:
            track_date = self._parse_date(as_of_date).strftime("%Y-%m-%d")
            themes = self.theme_tracker.track_all_themes(themes, track_date)

        return themes

    def _aggregate_structured_data(self, news_list: List[Dict]) -> Dict:
        """Aggregate structured data from multiple news items.

        Returns:
            Dict with:
            - all_entities: Counter of key_entities
            - all_keywords: Counter of keywords
            - event_type_counts: Counter of event_types
            - industry_counts: Counter of related_industries
            - high_importance_news: List of high importance news titles
        """
        from collections import Counter

        all_entities = Counter()
        all_keywords = Counter()
        event_type_counts = Counter()
        industry_counts = Counter()
        high_importance_news = []

        for news in news_list:
            structured = news.get("structured", {})

            # Aggregate entities
            for entity in structured.get("key_entities", []):
                all_entities[entity] += 1

            # Aggregate keywords
            for keyword in structured.get("keywords", []):
                all_keywords[keyword] += 1

            # Aggregate event types
            event_type = structured.get("event_type", "其他")
            event_type_counts[event_type] += 1

            # Aggregate industries
            for industry in structured.get("related_industries", []):
                industry_counts[industry] += 1

            # Collect high importance news
            importance = structured.get("importance", 0.5)
            if importance >= 0.7:
                high_importance_news.append({
                    "title": news.get("title", ""),
                    "importance": importance,
                    "event_type": event_type,
                })

        return {
            "all_entities": dict(all_entities),
            "all_keywords": dict(all_keywords),
            "event_type_counts": dict(event_type_counts),
            "industry_counts": dict(industry_counts),
            "high_importance_news": high_importance_news[:20],  # Top 20
            "total_news": len(news_list),
        }

    def _extract_themes_from_structured(
        self,
        aggregated: Dict,
        max_themes: int,
    ) -> List[Dict]:
        """Extract themes from aggregated structured data using LLM.

        Uses structured data (entities, keywords, industries) instead of raw text.
        Much more efficient than processing raw news.
        """
        # Build prompt with structured data
        prompt = self._build_structured_prompt(aggregated)

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            # Parse JSON from response
            themes = self._parse_response(content)

            return themes[:max_themes]

        except Exception as e:
            logger.error(
                "Structured theme extraction LLM failed, using keyword fallback",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {"stage": "theme_extract_structured_llm"}},
            )
            return self._fallback_from_structured(aggregated, max_themes)

    def _build_structured_prompt(self, aggregated: Dict) -> str:
        """Build LLM prompt from aggregated structured data."""

        # Format top entities and keywords
        top_entities = sorted(
            aggregated["all_entities"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:30]
        top_keywords = sorted(
            aggregated["all_keywords"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:30]
        top_industries = sorted(
            aggregated["industry_counts"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        # Format high importance news titles
        high_news_str = ""
        for news in aggregated["high_importance_news"]:
            high_news_str += f"- [{news['event_type']}] {news['title']}\n"

        # Calculate theme count
        theme_count = min(5, max(3, len(top_keywords) // 5))

        # Use string concatenation to avoid f-string formatting conflicts with JSON template
        prompt = """分析以下财经新闻聚合数据，提取""" + str(theme_count) + """个最有投资价值的主题。

【核心实体】（出现频次）
""" + self._format_counter_items(top_entities) + """

【关键词】（出现频次）
""" + self._format_counter_items(top_keywords) + """

【相关行业】（出现频次）
""" + self._format_counter_items(top_industries) + """

【事件类型分布】
""" + self._format_counter_items(list(aggregated['event_type_counts'].items())[:10]) + """

【重要新闻标题】（importance >= 0.7）
""" + (high_news_str if high_news_str else '无特别重要新闻') + """

【统计信息】
- 总新闻数: """ + str(aggregated['total_news']) + """
- 实体数: """ + str(len(aggregated['all_entities'])) + """
- 关键词数: """ + str(len(aggregated['all_keywords'])) + """

请按以下JSON格式输出：
{"themes": [{"name": "主题名称要具体如固态电池产业链而非新能源", "confidence": 0.85, "reason": "为什么看好这个主题基于数据简短说明", "keywords": ["关键词1", "关键词2", "关键词3"], "related_industries": ["行业1", "行业2"], "event_type": "主要事件类型如技术突破"}]}

【核心约束】
1. 只输出主题和关键词，严禁输出任何股票代码或公司名称
2. 主题要具体可操作（如AI算力服务器而非AI）
3. keywords要选择高频且有代表性的关键词从上面的关键词列表中选择
4. related_industries用申万行业名称从上面的行业列表中选择
5. 基于出现频次判断重要性，高频实体关键词更值得关注
6. 只输出JSON，不要其他内容"""

        return prompt

    def _format_counter_items(self, items: List) -> str:
        """Format counter items for prompt."""
        lines = []
        for item, count in items:
            lines.append(f"{item}: {count}")
        return "\n".join(lines)

    def _fallback_from_structured(self, aggregated: Dict, max_themes: int) -> List[Dict]:
        """Fallback theme extraction from structured data (no LLM)."""
        from .industry_mapper import IndustryMapper
        mapper = IndustryMapper()

        themes = []
        top_keywords = sorted(
            aggregated["all_keywords"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:max_themes * 2]

        # Group keywords by industry
        for kw, count in top_keywords[:max_themes]:
            industries = mapper.map_theme_to_industries(kw, use_llm_fallback=False)

            themes.append({
                "name": kw,
                "confidence": min(count / 10, 0.95),
                "reason": f"关键词'{kw}'出现{count}次",
                "keywords": [kw],
                "related_industries": industries,
                "event_type": aggregated["event_type_counts"] and max(
                    aggregated["event_type_counts"].items(),
                    key=lambda x: x[1]
                )[0] or "其他",
            })

        return themes

    def _count_related_news(self, theme: Dict, news_list: List[Dict]) -> int:
        """Count news items related to a theme."""
        keywords = set(kw.lower() for kw in theme.get("keywords", []))
        count = 0

        for news in news_list:
            structured = news.get("structured", {})
            news_keywords = set(kw.lower() for kw in structured.get("keywords", []))

            # Check if any theme keyword appears in news keywords
            if keywords & news_keywords:
                count += 1

        return count

    # ── Legacy API Methods (Fallback) ──────────────────────────────────────

    def get_news_for_recommendation(
        self,
        look_back_days: int = 1,
        max_articles: int = 1000,
        as_of_date: Optional[str] = None,
    ) -> List[Dict]:
        """Backward compat: Use cache if available, else API."""
        cached = self.get_cached_news_for_extraction(
            look_back_days,
            as_of_date=as_of_date,
        )

        if cached:
            return cached

        # Fallback to API
        return self._get_news_from_api(
            look_back_days,
            max_articles,
            as_of_date=as_of_date,
        )

    def _get_news_from_api(
        self,
        look_back_days: int,
        max_articles: int,
        as_of_date: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch news from API (fallback when cache empty)."""
        from tradingagents.dataflows.interface import route_to_vendor

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            if as_of_date and as_of_date[:10] != today:
                logger.warning(
                    "Skipping live recommendation-news fallback for historical date",
                    extra={"extra_data": {
                        "stage": "theme_extract_api_historical_skip",
                        "as_of_date": as_of_date,
                    }},
                )
                return []

            result = route_to_vendor(
                "get_recommendation_news",
                look_back_days,
                max_articles,
            )
            return self._parse_csv_to_list(result)

        except Exception as e:
            logger.error(
                "Recommendation news API failed during theme extraction",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {
                    "stage": "theme_extract_api",
                    "look_back_days": look_back_days,
                    "max_articles": max_articles,
                    "as_of_date": as_of_date,
                }},
            )
            return []

    def _parse_csv_to_list(self, csv_string: str) -> List[Dict]:
        """Parse CSV string result to list of news dicts."""
        return parse_recommendation_news_csv(csv_string)

    def extract_themes_from_api(
        self,
        look_back_days: int = 1,
        max_themes: int = 5,
        as_of_date: Optional[str] = None,
    ) -> List[Dict]:
        """Legacy method: Extract themes from API (not cache).

        Used as fallback when cache is empty.
        """
        news = self._get_news_from_api(look_back_days, 1000, as_of_date=as_of_date)
        if not news:
            return []

        themes = self.extract_themes(news, max_themes)
        return themes

    def extract_themes(
        self,
        news_list: List[Dict],
        max_themes: int = 5,
        max_news_for_llm: int = 500,
    ) -> List[Dict]:
        """Legacy method: Extract themes from raw news list.

        Kept for backward compatibility.
        """
        if not news_list:
            return []

        # Build concise news text for LLM
        news_items = []
        for i, news in enumerate(news_list[:max_news_for_llm]):
            title = news.get('title', '')
            content_summary = news.get('content', '')[:100]
            date = news.get('datetime', '')[:10] or ''
            source = news.get('data_source', '')
            news_items.append(f"{i+1}. [{date}][{source}] {title} | {content_summary}")

        news_text = "\n".join(news_items)

        prompt = f"""你是A股市场分析专家。分析以下财经新闻，提取3-5个最有投资价值的主题。

新闻列表（共{len(news_items)}条）：
{news_text}

请按以下JSON格式输出：
{
  "themes": [
    {
      "name": "主题名称（要具体，如'固态电池产业链'而非'新能源'）",
      "confidence": 0.85,
      "reason": "为什么看好这个主题（基于新闻内容简短说明）",
      "keywords": ["关键词1", "关键词2", "关键词3"],
      "related_industries": ["行业1", "行业2"]
    }
  ]
}

【核心约束】
1. 只输出主题和关键词，严禁输出任何股票代码或公司名称
2. 主题要具体可操作（如'AI算力服务器'而非'AI'）
3. 关键词用于后续搜索行业和股票，要简洁准确
4. related_industries 用申万行业名称（如'通信设备'、'计算机应用'）
5. 只输出JSON，不要其他内容"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            themes = self._parse_response(content)
            return themes[:max_themes]

        except Exception as e:
            logger.error(
                "Raw-news theme extraction LLM failed, using fallback",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {
                    "stage": "theme_extract_raw_llm",
                    "news_count": len(news_list),
                }},
            )
            return self._fallback_extract_themes(news_list, max_themes)

    def _fallback_extract_themes(self, news_list: List[Dict], max_themes: int) -> List[Dict]:
        """Fallback theme extraction using keyword matching."""
        from collections import Counter
        from .industry_mapper import IndustryMapper
        mapper = IndustryMapper()

        keyword_counts = Counter()
        important_keywords = [
            "AI", "人工智能", "大模型", "算力", "芯片", "半导体",
            "新能源", "光伏", "储能", "锂电池", "固态电池",
            "汽车", "电动车", "自动驾驶",
            "医药", "医疗", "创新药",
            "银行", "券商", "保险",
            "地产", "基建", "建材",
            "军工", "航天", "国防",
            "消费", "白酒", "食品",
            "5G", "通信", "物联网",
            "云计算", "大数据", "网络安全",
            "机器人", "自动化",
            "黄金", "有色", "稀土",
        ]

        for news in news_list:
            title = str(news.get("title", "") or "")
            for kw in important_keywords:
                if kw.lower() in title.lower():
                    keyword_counts[kw] += 1

        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)

        themes = []
        for kw, count in sorted_keywords[:max_themes]:
            industries = mapper.map_theme_to_industries(kw)
            themes.append({
                "name": kw,
                "confidence": min(count / 10, 1.0),
                "reason": f"今日{kw}相关新闻出现{count}次",
                "keywords": [kw],
                "related_industries": industries,
            })

        return themes

    def _parse_response(self, content: str) -> List[Dict]:
        """Parse LLM response to extract themes JSON."""
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)

        json_match = re.search(r"\{[\s\S]*themes[\s\S]*\}", content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data.get("themes", [])
            except json.JSONDecodeError:
                pass

        try:
            data = json.loads(content.strip())
            return data.get("themes", [])
        except json.JSONDecodeError:
            pass

        return []

    # ── Convenience Methods ─────────────────────────────────────────────────

    def get_today_themes(
        self,
        look_back_days: int = 1,
        with_tracking: bool = True,
        as_of_date: Optional[str] = None,
    ) -> List[Dict]:
        """Get today's themes (primary method).

        Uses cache by default, adds continuity tracking.
        """
        return self.extract_themes_from_cache(
            look_back_days=look_back_days,
            with_tracking=with_tracking,
            as_of_date=as_of_date,
        )

    def get_weekly_themes(
        self,
        week_start: str = None,
        with_tracking: bool = True,
        as_of_date: Optional[str] = None,
    ) -> List[Dict]:
        """Get weekly themes."""
        if week_start is None:
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            week_start = monday.strftime("%Y-%m-%d")

        return self.extract_themes_from_cache(
            look_back_days=7,
            with_tracking=with_tracking,
            as_of_date=as_of_date,
        )
