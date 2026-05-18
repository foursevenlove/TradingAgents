from tradingagents.recommendation.analysis_validator import (
    TradingAgentsValidationResult,
    normalize_graph_result,
)
from tradingagents.recommendation.news_parsing import parse_recommendation_news_csv
from tradingagents.recommendation.theme_extractor import ThemeExtractor


def test_parse_recommendation_news_csv_handles_quoted_commas():
    csv_text = """# 推荐系统热点新闻
title,content,datetime,data_source
"AI, 算力需求升温","多家公司发布, 新方案",2026-05-15 09:30:00,cls
"""

    rows = parse_recommendation_news_csv(csv_text)

    assert rows == [
        {
            "title": "AI, 算力需求升温",
            "content": "多家公司发布, 新方案",
            "datetime": "2026-05-15 09:30:00",
            "data_source": "cls",
        }
    ]


def test_theme_extractor_uses_explicit_as_of_date_for_cache_window():
    calls = []

    class FakeCache:
        def get_news_for_theme_extraction(self, start_date, end_date, min_importance):
            calls.append((start_date, end_date, min_importance))
            return []

    extractor = object.__new__(ThemeExtractor)
    extractor.cache_manager = FakeCache()

    result = extractor.get_cached_news_for_extraction(
        look_back_days=7,
        min_importance=0.4,
        as_of_date="2026-05-15",
    )

    assert result == []
    assert calls == [("2026-05-09", "2026-05-15", 0.4)]


def test_normalize_graph_result_accepts_tuple_return_from_trading_graph():
    final_state = {
        "final_trade_decision": "建议谨慎买入",
        "market_report": "市场报告" * 50,
        "news_report": "新闻报告" * 50,
    }

    result = normalize_graph_result((final_state, "BUY"), "600000.SH")

    assert result == TradingAgentsValidationResult(
        code="600000.SH",
        decision="BUY",
        confidence=0.0,
        market_summary=("市场报告" * 50)[:500],
        news_summary=("新闻报告" * 50)[:500],
        risk_summary="",
        reason="TradingAgents验证: BUY",
    )
