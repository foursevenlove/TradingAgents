"""News Preprocessor - LLM-based three-layer news processing.

Process each news item:
1. structured: key_entities, related_industries, event_type, importance, sentiment, keywords
2. content_summary: 100-char summary for quick preview
3. content_original: kept unchanged (stored separately in cache)
"""

import json
import re
from typing import Dict

from tradingagents.llm_clients import create_llm_client
from tradingagents.default_config import DEFAULT_CONFIG


class NewsPreprocessor:
    """Process news with LLM to extract structured information."""

    def __init__(self, config: Dict = None):
        self.config = config or DEFAULT_CONFIG

        # Use quick_think LLM for preprocessing (cost-effective)
        client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
        )
        self.llm = client.get_llm()

    def process_news(self, news: Dict) -> Dict:
        """Process a news item and return three-layer data.

        Args:
            news: Dict with 'title', 'content_original' (optional)

        Returns:
            Dict with:
            - structured: Dict with key_entities, related_industries, event_type, importance, sentiment, keywords
            - content_summary: 100-char summary
        """
        title = news.get("title", "")
        content = news.get("content_original", "")
        source = news.get("source", "")

        # Build prompt
        prompt = self._build_prompt(title, content, source)

        try:
            response = self.llm.invoke(prompt)
            content_str = response.content if hasattr(response, "content") else str(response)

            # Parse JSON from response
            parsed = self._parse_response(content_str)

            return {
                "structured": parsed,
                "content_summary": parsed.get("summary", ""),
            }

        except Exception as e:
            # Fallback: minimal structured info without LLM
            print(f"[NewsPreprocessor] LLM error: {e}, using fallback")
            return self._fallback_process(title, content)

    def _build_prompt(self, title: str, content: str, source: str) -> str:
        """Build LLM prompt for news processing."""

        # Truncate content if too long (keep key info)
        content_for_llm = content[:800] if content else ""

        # Use string concatenation to avoid f-string formatting conflicts with JSON template
        prompt = """分析以下财经新闻，提取结构化信息。

标题: """ + title + """
内容: """ + content_for_llm + """
来源: """ + source + """

请输出JSON（不要遗漏任何重要信息）：
{"key_entities": ["所有核心实体（公司名、产品名、技术名、政策名、人名等）"], "related_industries": ["相关申万行业（如电池、半导体、通信设备、医药生物）"], "event_type": "技术突破|政策发布|业绩公告|并购重组|产品发布|市场动态|其他", "importance": "0.0-1.0重要性评分（政策发布/技术突破=0.8+，重要公司公告=0.6+，泛泛报道=0.3）", "sentiment": "positive|negative|neutral", "summary": "摘要100字内保留关键信息谁做了什么有什么影响", "keywords": ["后续可用于主题匹配的关键词核心概念词"]}

【核心约束】
1. key_entities和keywords不要遗漏任何重要信息，数量不限
2. importance评分要合理：重大政策/技术突破给高分，重复/无实质内容的报道给低分
3. summary要简洁但保留关键点（谁做了什么，有什么影响）
4. 只输出JSON，不要其他内容"""

        return prompt

    def _parse_response(self, content: str) -> Dict:
        """Parse LLM response to extract JSON."""
        # Remove markdown code block if present
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)

        # Try to find JSON object
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return self._validate_and_normalize(data)
            except json.JSONDecodeError:
                pass

        # Fallback: try to parse without regex
        try:
            data = json.loads(content.strip())
            return self._validate_and_normalize(data)
        except json.JSONDecodeError:
            pass

        return self._empty_structured()

    def _validate_and_normalize(self, data: Dict) -> Dict:
        """Validate and normalize structured data."""
        result = self._empty_structured()

        # key_entities: list of strings
        if "key_entities" in data:
            entities = data["key_entities"]
            if isinstance(entities, list):
                result["key_entities"] = [str(e) for e in entities if e]

        # related_industries: list of strings
        if "related_industries" in data:
            industries = data["related_industries"]
            if isinstance(industries, list):
                result["related_industries"] = [str(i) for i in industries if i]

        # event_type: validate against known types
        valid_event_types = [
            "技术突破", "政策发布", "业绩公告", "并购重组",
            "产品发布", "市场动态", "其他"
        ]
        if "event_type" in data:
            event_type = str(data["event_type"])
            if event_type in valid_event_types:
                result["event_type"] = event_type
            else:
                result["event_type"] = "其他"

        # importance: float 0.0-1.0
        if "importance" in data:
            try:
                importance = float(data["importance"])
                result["importance"] = max(0.0, min(1.0, importance))
            except (TypeError, ValueError):
                result["importance"] = 0.5

        # sentiment: validate against known values
        valid_sentiments = ["positive", "negative", "neutral"]
        if "sentiment" in data:
            sentiment = str(data["sentiment"]).lower()
            if sentiment in valid_sentiments:
                result["sentiment"] = sentiment
            else:
                result["sentiment"] = "neutral"

        # summary: string, max 150 chars
        if "summary" in data:
            summary = str(data["summary"])
            result["summary"] = summary[:150]

        # keywords: list of strings
        if "keywords" in data:
            keywords = data["keywords"]
            if isinstance(keywords, list):
                result["keywords"] = [str(k) for k in keywords if k]

        return result

    def _empty_structured(self) -> Dict:
        """Return empty structured data template."""
        return {
            "key_entities": [],
            "related_industries": [],
            "event_type": "其他",
            "importance": 0.5,
            "sentiment": "neutral",
            "summary": "",
            "keywords": [],
        }

    def _fallback_process(self, title: str, content: str) -> Dict:
        """Fallback processing without LLM (keyword-based)."""

        # Simple keyword extraction from title
        keywords = []
        important_keywords = [
            "AI", "人工智能", "大模型", "算力", "芯片", "半导体",
            "新能源", "光伏", "储能", "锂电池", "固态电池",
            "汽车", "电动车", "自动驾驶", "智能驾驶",
            "医药", "医疗", "创新药", "生物",
            "银行", "券商", "保险", "金融",
            "地产", "基建", "建材",
            "军工", "航天", "国防",
            "消费", "白酒", "食品",
            "5G", "通信", "物联网",
            "云计算", "大数据", "网络安全",
            "机器人", "自动化",
            "黄金", "有色", "稀土",
            "政策", "发布", "公告", "业绩", "并购", "重组",
        ]

        title_lower = title.lower()
        for kw in important_keywords:
            if kw.lower() in title_lower:
                keywords.append(kw)

        # Infer event_type from title
        event_type = "其他"
        if any(kw in title for kw in ["政策", "发布", "通知", "规定", "文件"]):
            event_type = "政策发布"
        elif any(kw in title for kw in ["突破", "创新", "研发", "技术", "专利"]):
            event_type = "技术突破"
        elif any(kw in title for kw in ["业绩", "财报", "利润", "营收"]):
            event_type = "业绩公告"
        elif any(kw in title for kw in ["并购", "重组", "收购", "合并"]):
            event_type = "并购重组"
        elif any(kw in title for kw in ["发布", "推出", "上线", "新品"]):
            event_type = "产品发布"

        # Infer importance from event_type and keywords
        importance = 0.5
        if event_type in ["政策发布", "技术突破"]:
            importance = 0.8
        elif event_type in ["并购重组", "业绩公告"]:
            importance = 0.6
        elif len(keywords) >= 3:
            importance = 0.5
        else:
            importance = 0.3

        # Infer sentiment from title
        sentiment = "neutral"
        if any(kw in title for kw in ["涨", "升", "增", "利好", "突破", "创新", "增长"]):
            sentiment = "positive"
        elif any(kw in title for kw in ["跌", "降", "减", "利空", "亏损", "下滑", "风险"]):
            sentiment = "negative"

        # Generate simple summary from title
        summary = title[:100]

        return {
            "structured": {
                "key_entities": keywords[:5],
                "related_industries": keywords[:3],
                "event_type": event_type,
                "importance": importance,
                "sentiment": sentiment,
                "summary": summary,
                "keywords": keywords,
            },
            "content_summary": summary,
        }


# Batch processor for efficiency
class BatchPreprocessor:
    """Process multiple news items in batch."""

    def __init__(self):
        self.preprocessor = NewsPreprocessor()

    def process_batch(self, news_list: list, max_batch: int = 50) -> list:
        """Process a batch of news items.

        Args:
            news_list: List of news dicts
            max_batch: Maximum items to process in one call

        Returns:
            List of processed results
        """
        results = []

        for news in news_list[:max_batch]:
            try:
                processed = self.preprocessor.process_news(news)
                results.append({
                    "news_id": news.get("news_id"),
                    "processed": processed,
                })
            except Exception as e:
                print(f"[BatchPreprocessor] Error processing {news.get('news_id')}: {e}")
                continue

        return results