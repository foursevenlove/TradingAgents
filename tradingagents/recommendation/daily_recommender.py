"""Daily Recommender - Generate daily stock recommendations.

Integrates:
1. ThemeExtractor: Get investment themes from news
2. StockScreener: Screen candidate stocks
3. IndustryMapper: Map themes to stocks
4. Optional: Deep analysis with TradingAgentsGraph (light mode: market + news)
"""

from datetime import datetime
import logging
from typing import List, Dict, Optional
import pandas as pd

from tradingagents.recommendation.theme_extractor import ThemeExtractor
from tradingagents.recommendation.stock_screener import StockScreener
from tradingagents.recommendation.industry_mapper import IndustryMapper
from tradingagents.recommendation.analysis_validator import TradingAgentsValidator
from tradingagents.default_config import DEFAULT_CONFIG


logger = logging.getLogger("tradingagents.web.recommendation.daily")


class DailyRecommender:
    """Generate daily stock recommendations."""

    def __init__(self):
        self.theme_extractor = ThemeExtractor()
        self.stock_screener = StockScreener()
        self.industry_mapper = IndustryMapper()

    def run_light_analysis(
        self,
        stock_code: str,
        trade_date: str,
    ) -> Dict:
        """Run light analysis on a stock (market + news analysts only).

        Uses minimal debate rounds for speed while providing validation.

        Args:
            stock_code: Stock ticker (e.g., "000001.SZ")
            trade_date: Trade date (YYYY-MM-DD)

        Returns:
            Dict with analysis results: decision, confidence, summary
        """
        # Configure for light analysis
        light_config = DEFAULT_CONFIG.copy()
        light_config["max_debate_rounds"] = 1  # Minimum debate
        light_config["max_risk_discuss_rounds"] = 1

        try:
            validator = TradingAgentsValidator(
                selected_analysts=["market", "news"],
                config=light_config,
                debug=False,
            )
            return validator.validate(stock_code, trade_date)

        except Exception as e:
            logger.error(
                "Light TradingAgents analysis failed for recommendation stock",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {
                    "stage": "daily_recommend_light_analysis",
                    "ticker": stock_code,
                    "trade_date": trade_date,
                }},
            )
            # Fallback: return basic info without analysis
            return {
                "code": stock_code,
                "decision": "hold",
                "confidence": 0.0,
                "reason": f"分析失败: {str(e)[:100]}",
            }

    def generate_recommendations(
        self,
        trade_date: str = None,
        max_themes: int = 5,
        max_stocks_per_theme: int = 3,
        min_amount: float = 1e8,
        with_deep_analysis: bool = False,
    ) -> Dict:
        """Generate daily recommendations.

        Workflow:
        1. Extract themes from news (look_back_days=1)
        2. Screen stocks by technical/volume factors
        3. Map themes to stocks by industry
        4. Optional: Run light analysis validation
        5. Return recommendations

        Args:
            trade_date: Trade date (YYYY-MM-DD). Default today.
            max_themes: Maximum themes to extract
            max_stocks_per_theme: Maximum stocks per theme
            min_amount: Minimum trading amount for screening
            with_deep_analysis: Whether to run TradingAgentsGraph light analysis

        Returns:
            Dict with:
                - themes: List of theme dicts
                - stocks: Dict mapping theme to stock list
                - analysis: Dict mapping stock code to analysis result (if enabled)
                - summary: Markdown summary
                - timestamp: Generation timestamp
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        # 1. Extract themes from news (daily: look_back_days=1)
        themes = self.theme_extractor.extract_themes_from_cache(
            look_back_days=1,
            max_themes=max_themes,
            as_of_date=trade_date,
        )

        # 2. Screen stocks
        screened_stocks = self.stock_screener.screen(
            min_change_pct=0,  # Only positive change today
            max_change_pct=15,
            min_amount=min_amount,
            top_n=100,
        )

        # 3. Map themes to stocks
        theme_stocks = self.industry_mapper.map_all_themes(
            themes,
            screened_stocks,
            max_per_theme=max_stocks_per_theme,
        )

        # 4. Optional: Run deep analysis on recommended stocks
        analysis_results = {}
        if with_deep_analysis:
            # Collect all unique stock codes
            all_codes = set()
            for stocks in theme_stocks.values():
                for stock in stocks:
                    code = stock.get("code", "")
                    if code:
                        # Convert to ticker format (e.g., "000001" -> "000001.SZ")
                        if not "." in code:
                            # Infer exchange from code prefix
                            if code.startswith("6"):
                                ticker = f"{code}.SH"
                            else:
                                ticker = f"{code}.SZ"
                        else:
                            ticker = code
                        all_codes.add(ticker)

            # Run analysis for each stock (limit to first 5 for speed)
            for ticker in list(all_codes)[:5]:
                try:
                    analysis = self.run_light_analysis(ticker, trade_date)
                    analysis_results[ticker.split(".")[0]] = analysis
                    # Update stock dict with analysis result
                    for theme, stocks in theme_stocks.items():
                        for stock in stocks:
                            if stock.get("code") == ticker.split(".")[0]:
                                stock["decision"] = analysis["decision"]
                                stock["confidence"] = analysis["confidence"]
                                stock["analysis_reason"] = analysis.get("reason", "")
                except Exception as exc:
                    logger.error(
                        "Skipping recommendation light analysis after failure",
                        exc_info=(type(exc), exc, exc.__traceback__),
                        extra={"extra_data": {
                            "stage": "daily_recommend_deep_analysis_loop",
                            "ticker": ticker,
                            "trade_date": trade_date,
                        }},
                    )

        # 5. Generate summary
        summary = self._generate_summary(themes, theme_stocks, trade_date, analysis_results if with_deep_analysis else None)

        return {
            "themes": themes,
            "stocks": theme_stocks,
            "analysis": analysis_results,
            "summary": summary,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trade_date": trade_date,
        }

    def _generate_summary(
        self,
        themes: List[Dict],
        theme_stocks: Dict[str, List[Dict]],
        trade_date: str,
        analysis_results: Dict = None,
    ) -> str:
        """Generate markdown summary of recommendations."""

        lines = [
            f"# 每日股票推荐 - {trade_date}",
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 今日热点主题",
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
            lines.append(f"- 理由: {reason}")
            lines.append(f"- 关键词: {', '.join(keywords)}")
            lines.append("")

        # Recommended stocks
        lines.append("## 推荐股票")
        lines.append("")

        for theme_name, stocks in theme_stocks.items():
            if not stocks:
                continue

            lines.append(f"### {theme_name}")
            lines.append("")

            # Add analysis columns if available
            if analysis_results:
                lines.append("| 代码 | 名称 | 价格 | 涨幅 | 行业 | 决策 | 置信度 | 推荐理由 |")
                lines.append("|------|------|------|------|------|------|--------|----------|")
            else:
                lines.append("| 代码 | 名称 | 价格 | 涨幅 | 行业 | 推荐理由 |")
                lines.append("|------|------|------|------|------|----------|")

            for stock in stocks:
                code = stock.get("code", "")
                name = stock.get("name", "")
                price = stock.get("price", 0)
                change = stock.get("change_pct", 0)
                industry = stock.get("industry", "")
                reason = stock.get("reason", "")

                if analysis_results and code in analysis_results:
                    analysis = analysis_results[code]
                    decision = analysis.get("decision", "hold")
                    confidence = analysis.get("confidence", 0)
                    analysis_reason = stock.get("analysis_reason", "")
                    combined_reason = f"{reason}; {analysis_reason}"
                    lines.append(
                        f"| {code} | {name} | {price:.2f} | {change:.2f}% | {industry} | {decision} | {confidence:.0%} | {combined_reason} |"
                    )
                else:
                    lines.append(
                        f"| {code} | {name} | {price:.2f} | {change:.2f}% | {industry} | {reason} |"
                    )

            lines.append("")

        # Disclaimer
        lines.append("---")
        lines.append("")
        lines.append("**免责声明**: 本推荐仅供参考，不构成投资建议。投资有风险，入市需谨慎。")
        lines.append("")

        return "\n".join(lines)

    def get_quick_recommendations(
        self,
        top_n: int = 5,
    ) -> List[Dict]:
        """Get quick recommendations without full workflow.

        Just returns top gainers with highest scores.

        Args:
            top_n: Number of stocks

        Returns:
            List of stock dicts
        """
        df = self.stock_screener.get_top_gainers(top_n)

        results = []
        for _, row in df.iterrows():
            results.append({
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "price": row.get("price", 0),
                "change_pct": row.get("change_pct", 0),
                "amount": row.get("amount", 0),
                "score": row.get("score", 0),
                "reason": f"涨幅{row.get('change_pct', 0):.2f}%，成交额大",
            })

        return results


def run_daily_recommendation(
    trade_date: str = None,
    output_format: str = "markdown",
) -> str:
    """Run daily recommendation and return result.

    Args:
        trade_date: Trade date (YYYY-MM-DD)
        output_format: Output format ('markdown' or 'json')

    Returns:
        Recommendation report string
    """
    recommender = DailyRecommender()
    result = recommender.generate_recommendations(trade_date)

    if output_format == "json":
        import json
        # Remove summary for JSON output
        json_result = {
            "themes": result["themes"],
            "stocks": result["stocks"],
            "timestamp": result["timestamp"],
            "trade_date": result["trade_date"],
        }
        return json.dumps(json_result, ensure_ascii=False, indent=2)

    return result["summary"]
