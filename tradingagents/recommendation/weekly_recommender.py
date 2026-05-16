"""Weekly Recommender - Generate weekly deep stock recommendations.

Integrates:
1. WeeklyThemeExtractor: Aggregate themes from week's news
2. StockScreener: Screen candidate stocks with weekly metrics
3. IndustryMapper: Map themes to stocks
4. Deep analysis with full TradingAgentsGraph (all analysts)
"""

from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import pandas as pd

from tradingagents.recommendation.theme_extractor import ThemeExtractor
from tradingagents.recommendation.stock_screener import StockScreener
from tradingagents.recommendation.industry_mapper import IndustryMapper
from tradingagents.default_config import DEFAULT_CONFIG


logger = logging.getLogger("tradingagents.web.recommendation.weekly")


class WeeklyRecommender:
    """Generate weekly stock recommendations with full analysis."""

    def __init__(self):
        self.theme_extractor = ThemeExtractor()
        self.stock_screener = StockScreener()
        self.industry_mapper = IndustryMapper()

    def run_full_analysis(
        self,
        stock_code: str,
        trade_date: str,
    ) -> Dict:
        """Run full analysis on a stock (all 4 analysts + full debate).

        Args:
            stock_code: Stock ticker (e.g., "000001.SZ")
            trade_date: Trade date (YYYY-MM-DD)

        Returns:
            Dict with analysis results: decision, confidence, full report
        """
        try:
            from tradingagents.graph.trading_graph import TradingAgentsGraph

            # Create graph with all analysts
            graph = TradingAgentsGraph(
                selected_analysts=["market", "social", "news", "fundamentals"],
                debug=False,
                config=DEFAULT_CONFIG,
            )

            # Run analysis
            state = graph.propagate(stock_code, trade_date)

            # Extract decision signal
            decision = state.get("final_decision", "hold")
            confidence = state.get("final_decision_confidence", 0.5)

            # Get all analyst reports
            reports = {}
            for key in ["market_analyst_report", "news_analyst_report",
                       "social_analyst_report", "fundamentals_analyst_report"]:
                if key in state:
                    reports[key] = state[key][:1000]  # Limit length

            # Risk assessment
            risk_summary = ""
            if "risk_manager_decision" in state:
                risk_summary = state["risk_manager_decision"][:500]

            return {
                "code": stock_code,
                "decision": decision,
                "confidence": confidence,
                "reports": reports,
                "risk_summary": risk_summary,
                "reason": f"完整分析: {decision} (置信度{confidence:.0%})",
            }

        except Exception as e:
            logger.error(
                "Weekly full TradingAgents analysis failed",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {
                    "stage": "weekly_recommend_full_analysis",
                    "ticker": stock_code,
                    "trade_date": trade_date,
                }},
            )
            return {
                "code": stock_code,
                "decision": "hold",
                "confidence": 0.0,
                "reason": f"分析失败: {str(e)[:100]}",
            }

    def get_weekly_news(
        self,
        week_start: str,
        days: int = 7,
        max_articles: int = 3000,  # 每周推荐获取更多新闻
    ) -> List[Dict]:
        """Aggregate news from multiple days in a week.

        Args:
            week_start: Start date (YYYY-MM-DD)
            days: Number of days to aggregate (default 7 trading days)
            max_articles: Maximum news articles to fetch

        Returns:
            List of news dicts
        """
        # Single API call for the whole week (more efficient)
        try:
            news = self.theme_extractor.get_news_for_recommendation(
                look_back_days=days,
                max_articles=max_articles,
            )
            return news
        except Exception as exc:
            logger.error(
                "Weekly recommendation news fetch failed",
                exc_info=(type(exc), exc, exc.__traceback__),
                extra={"extra_data": {
                    "stage": "weekly_recommend_news_fetch",
                    "week_start": week_start,
                    "days": days,
                    "max_articles": max_articles,
                }},
            )
            return []

    def extract_weekly_themes(
        self,
        week_start: str,
        max_themes: int = 10,
        max_news_for_llm: int = 2000,  # 每周推荐用更多新闻
    ) -> List[Dict]:
        """Extract themes from weekly aggregated news.

        Args:
            week_start: Start date (YYYY-MM-DD)
            max_themes: Maximum themes to extract
            max_news_for_llm: Maximum news to send to LLM (default 2000 for weekly)

        Returns:
            List of theme dicts
        """
        news = self.get_weekly_news(week_start)
        if not news:
            return []

        themes = self.theme_extractor.extract_themes(
            news,
            max_themes=max_themes,
            max_news_for_llm=max_news_for_llm,
        )

        # Add week context to each theme
        for theme in themes:
            theme["week"] = week_start
            # Boost confidence for recurring themes
            if "confidence" in theme:
                theme["confidence"] = min(theme["confidence"] + 0.1, 0.95)

        return themes

    def generate_recommendations(
        self,
        week_start: str = None,
        max_themes: int = 10,
        max_stocks_per_theme: int = 5,
        min_amount: float = 5e8,  # Higher threshold for weekly
        max_analysis_stocks: int = 10,
    ) -> Dict:
        """Generate weekly recommendations with full deep analysis.

        Workflow:
        1. Aggregate news from the week
        2. Extract themes (weekly perspective)
        3. Screen stocks with stricter criteria
        4. Map themes to stocks
        5. Run full analysis on top candidates

        Args:
            week_start: Week start date (YYYY-MM-DD). Default this week.
            max_themes: Maximum themes to extract
            max_stocks_per_theme: Maximum stocks per theme
            min_amount: Minimum trading amount (higher for weekly)
            max_analysis_stocks: Maximum stocks to run full analysis on

        Returns:
            Dict with themes, stocks, analysis, summary, week info
        """
        if week_start is None:
            # Default to this week's Monday
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            week_start = monday.strftime("%Y-%m-%d")

        week_end = (datetime.strptime(week_start, "%Y-%m-%d") +
                    timedelta(days=4)).strftime("%Y-%m-%d")

        # 1. Extract themes from weekly news
        themes = self.extract_weekly_themes(week_start, max_themes)

        # 2. Screen stocks with same criteria as daily (more flexible)
        screened_stocks = self.stock_screener.screen(
            min_change_pct=0,  # Same as daily, allow positive change
            max_change_pct=30,
            min_amount=min_amount,
            top_n=200,
        )

        # 3. Map themes to stocks
        theme_stocks = self.industry_mapper.map_all_themes(
            themes,
            screened_stocks,
            max_per_theme=max_stocks_per_theme,
        )

        # 4. Run full analysis on top candidates
        analysis_results = {}

        # Collect unique stocks
        all_codes = set()
        for stocks in theme_stocks.values():
            for stock in stocks:
                code = stock.get("code", "")
                if code:
                    if "." not in code:
                        ticker = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
                    else:
                        ticker = code
                    all_codes.add(ticker)

        # Run full analysis (limit for speed)
        for ticker in list(all_codes)[:max_analysis_stocks]:
            try:
                analysis = self.run_full_analysis(ticker, week_end)
                code = ticker.split(".")[0]
                analysis_results[code] = analysis

                # Update stock dict
                for theme, stocks in theme_stocks.items():
                    for stock in stocks:
                        if stock.get("code") == code:
                            stock["decision"] = analysis["decision"]
                            stock["confidence"] = analysis["confidence"]
                            stock["analysis_reason"] = analysis.get("reason", "")
            except Exception as exc:
                logger.error(
                    "Skipping weekly full analysis after failure",
                    exc_info=(type(exc), exc, exc.__traceback__),
                    extra={"extra_data": {
                        "stage": "weekly_recommend_analysis_loop",
                        "ticker": ticker,
                        "week_end": week_end,
                    }},
                )

        # 5. Generate summary
        summary = self._generate_summary(
            themes, theme_stocks, analysis_results,
            week_start, week_end,
        )

        return {
            "week_start": week_start,
            "week_end": week_end,
            "themes": themes,
            "stocks": theme_stocks,
            "analysis": analysis_results,
            "summary": summary,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _generate_summary(
        self,
        themes: List[Dict],
        theme_stocks: Dict[str, List[Dict]],
        analysis_results: Dict,
        week_start: str,
        week_end: str,
    ) -> str:
        """Generate markdown summary of weekly recommendations."""

        lines = [
            f"# 每周股票推荐 - {week_start} 至 {week_end}",
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 本周热点主题分析",
            "",
        ]

        # Themes summary
        for theme in themes:
            name = theme.get("name", "未知主题")
            confidence = theme.get("confidence", 0)
            reason = theme.get("reason", "")
            keywords = theme.get("keywords", [])

            lines.append(f"### {name}")
            lines.append(f"- 置信度: {confidence:.0%}")
            lines.append(f"- 分析依据: {reason}")
            lines.append(f"- 关键词: {', '.join(keywords)}")
            lines.append("")

        # Recommended stocks with analysis
        lines.append("## 推荐股票（完整分析）")
        lines.append("")

        for theme_name, stocks in theme_stocks.items():
            if not stocks:
                continue

            lines.append(f"### {theme_name}")
            lines.append("")
            lines.append("| 代码 | 名称 | 价格 | 涨幅 | 行业 | 决策 | 置信度 | 分析结论 |")
            lines.append("|------|------|------|------|------|------|--------|----------|")

            for stock in stocks:
                code = stock.get("code", "")
                name = stock.get("name", "")
                price = stock.get("price", 0)
                change = stock.get("change_pct", 0)
                industry = stock.get("industry", "")

                if code in analysis_results:
                    analysis = analysis_results[code]
                    decision = analysis.get("decision", "hold")
                    confidence = analysis.get("confidence", 0)
                    reason = stock.get("analysis_reason", analysis.get("reason", ""))
                    lines.append(
                        f"| {code} | {name} | {price:.2f} | {change:.2f}% | {industry} | {decision} | {confidence:.0%} | {reason} |"
                    )
                else:
                    lines.append(
                        f"| {code} | {name} | {price:.2f} | {change:.2f}% | {industry} | - | - | 未分析 |"
                    )

            lines.append("")

        # Disclaimer
        lines.append("---")
        lines.append("")
        lines.append("**免责声明**: 本推荐仅供参考，不构成投资建议。投资有风险，入市需谨慎。")
        lines.append("")

        return "\n".join(lines)


def run_weekly_recommendation(
    week_start: str = None,
    output_format: str = "markdown",
) -> str:
    """Run weekly recommendation and return result.

    Args:
        week_start: Week start date (YYYY-MM-DD)
        output_format: Output format ('markdown' or 'json')

    Returns:
        Recommendation report string
    """
    recommender = WeeklyRecommender()
    result = recommender.generate_recommendations(week_start)

    if output_format == "json":
        import json
        json_result = {
            "week_start": result["week_start"],
            "week_end": result["week_end"],
            "themes": result["themes"],
            "stocks": result["stocks"],
            "analysis": result["analysis"],
            "timestamp": result["timestamp"],
        }
        return json.dumps(json_result, ensure_ascii=False, indent=2)

    return result["summary"]
