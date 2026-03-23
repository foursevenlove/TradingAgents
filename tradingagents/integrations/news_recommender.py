"""基于新闻的股票推荐器"""
from typing import List, Dict, Optional
from tradingagents.llm_clients import create_llm_client
from tradingagents.default_config import DEFAULT_CONFIG


class NewsBasedRecommender:
    """基于新闻推荐股票"""

    def __init__(self, config: Dict = None):
        self.config = config or DEFAULT_CONFIG

        # 使用快速模型做主题提取
        client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
        )
        self.llm = client.get_llm()

    def extract_themes(self, news_list: List[Dict]) -> Dict:
        """从新闻中提取投资主题

        Args:
            news_list: 新闻列表

        Returns:
            主题分析结果
        """
        # 构建新闻摘要
        news_text = "\n".join([
            f"{i+1}. {news['title']}"
            for i, news in enumerate(news_list[:20])
        ])

        prompt = f"""你是A股市场分析专家。分析以下今日财经新闻，提取3-5个最有投资价值的主题。

新闻列表：
{news_text}

请按以下JSON格式输出：
{{
  "themes": [
    {{
      "name": "主题名称",
      "confidence": 0.9,
      "reason": "为什么看好这个主题",
      "keywords": ["关键词1", "关键词2"],
      "related_industries": ["行业1", "行业2"],
      "stock_examples": ["股票代码1", "股票代码2"]
    }}
  ]
}}

要求：
1. 主题要具体（如"AI大模型"而非"科技"）
2. 优先选择有政策支持或突发利好的主题
3. stock_examples给出2-3个A股代码（如000001.SZ）
4. 只输出JSON，不要其他内容
"""

        response = self.llm.invoke(prompt)
        return self._parse_response(response.content)

    def _parse_response(self, content: str) -> Dict:
        """解析LLM响应"""
        import json
        import re

        # 提取JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        return {"themes": []}

    def recommend_stocks(self, news_list: List[Dict], top_n: int = 10) -> List[Dict]:
        """推荐股票

        Args:
            news_list: 新闻列表
            top_n: 推荐数量

        Returns:
            推荐股票列表
        """
        # 提取主题
        themes_result = self.extract_themes(news_list)
        themes = themes_result.get("themes", [])

        if not themes:
            return []

        # 收集所有推荐的股票
        recommendations = []
        for theme in themes:
            for stock_code in theme.get("stock_examples", []):
                recommendations.append({
                    "ticker": stock_code,
                    "theme": theme["name"],
                    "reason": theme["reason"],
                    "confidence": theme["confidence"]
                })

        # 去重并返回
        seen = set()
        unique_recs = []
        for rec in recommendations:
            if rec["ticker"] not in seen:
                seen.add(rec["ticker"])
                unique_recs.append(rec)

        return unique_recs[:top_n]
