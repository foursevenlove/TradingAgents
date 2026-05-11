"""API routes for stock recommendation."""
import datetime
from typing import Optional
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query

from .recommend_history_manager import get_history_manager

router = APIRouter(prefix="/api/recommend", tags=["recommendation"])


# ── News Cache Status ─────────────────────────────────────────────────────

@router.get("/cache/status")
async def get_cache_status():
    """获取新闻缓存状态。

    Returns:
        Dict with cache stats: total_news, processed_news, date_range, last_update
    """
    from tradingagents.recommendation.news_cache_manager import get_cache_manager

    cache = get_cache_manager()
    stats = cache.get_cache_stats()

    return {
        "status": "running" if cache._running else "stopped",
        "total_news": stats["total_news"],
        "processed_news": stats["processed_news"],
        "unprocessed_news": stats["unprocessed_news"],
        "total_themes": stats["total_themes"],
        "date_range": stats["date_range"],
        "last_update": stats["last_update"],
    }


@router.get("/cache/trigger-update")
async def trigger_cache_update():
    """手动触发缓存更新（通常由后台自动执行）。

    Returns:
        Dict with update result
    """
    from tradingagents.recommendation.news_cache_manager import get_cache_manager

    cache = get_cache_manager()
    cache._do_update()

    stats = cache.get_cache_stats()
    return {
        "message": "Cache update triggered",
        "stats": stats,
    }


# ── Trending Themes ───────────────────────────────────────────────────────

@router.get("/themes/trending")
async def get_trending_themes(
    days: int = Query(7, description="回溯天数"),
    min_consecutive: int = Query(2, description="最小连续天数"),
):
    """获取持续热点主题（连续多天出现）。

    Returns:
        List of trending themes with continuity info
    """
    from tradingagents.recommendation.theme_tracker import ThemeTracker

    tracker = ThemeTracker()
    trending = tracker.get_trending_themes(days=days, min_consecutive=min_consecutive)

    return {
        "days": days,
        "min_consecutive": min_consecutive,
        "total": len(trending),
        "themes": trending,
    }


@router.get("/themes/new-hotspots")
async def get_new_hotspots(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
):
    """获取新热点主题（首次出现）。

    Returns:
        List of new hotspot themes
    """
    from tradingagents.recommendation.theme_tracker import ThemeTracker

    if date is None:
        date = datetime.date.today().isoformat()

    tracker = ThemeTracker()
    hotspots = tracker.get_new_hotspots(date)

    return {
        "date": date,
        "total": len(hotspots),
        "themes": hotspots,
    }


# ── Latest Cached Results ────────────────────────────────────────────────

@router.get("/latest")
async def get_latest_recommendations():
    """获取所有模式的上一次推荐结果。

    Returns:
        Dict with daily, weekly, top results (if exists)
    """
    manager = get_history_manager()

    result = {
        "daily": None,
        "weekly": None,
        "top": None,
    }

    # Get latest daily
    daily_record = manager.get_latest_result("daily")
    if daily_record:
        result["daily"] = daily_record["result"]

    # Get latest weekly
    weekly_record = manager.get_latest_result("weekly")
    if weekly_record:
        result["weekly"] = weekly_record["result"]

    # Get latest top
    top_record = manager.get_latest_result("top")
    if top_record:
        result["top"] = top_record["result"]

    return result


@router.get("/latest/{mode}")
async def get_latest_by_mode(mode: str):
    """获取指定模式的上一次推荐结果。

    Args:
        mode: 'daily', 'weekly', or 'top'

    Returns:
        Dict with result data or None
    """
    if mode not in ["daily", "weekly", "top"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'daily', 'weekly', or 'top'")

    manager = get_history_manager()
    record = manager.get_latest_result(mode)

    if record:
        return record["result"]
    return {"exists": False, "message": "No cached result found"}


@router.get("/history")
async def list_history(
    mode: Optional[str] = Query(None, description="筛选模式 (daily/weekly/top)"),
    limit: int = Query(10, description="返回数量"),
):
    """获取推荐历史记录列表。

    Returns:
        List of history records
    """
    manager = get_history_manager()
    history = manager.list_history(mode=mode, limit=limit)
    return {"total": len(history), "records": history}


# ── Daily Recommendation ──────────────────────────────────────────────────

@router.get("/daily")
async def recommend_daily(
    trade_date: Optional[str] = Query(None, description="交易日期 (YYYY-MM-DD)"),
    max_themes: int = Query(5, description="最大主题数量"),
    max_stocks: int = Query(5, description="每个主题最大股票数"),
    min_amount: float = Query(1e8, description="最小成交额（元）"),
    with_analysis: bool = Query(False, description="是否运行深度分析验证"),
    refresh: bool = Query(False, description="强制重新生成（忽略缓存）"),
):
    """获取每日股票推荐。

    流程：
    1. 从Tushare获取财经新闻
    2. LLM提取投资主题（只给方向，不给代码）
    3. 篛选高成交量股票
    4. 按主题关键词匹配行业
    5. 可选：运行深度分析验证

    Args:
        refresh: 若为False，优先返回缓存结果

    Returns:
        Dict with themes, stocks, analysis, summary
    """
    from tradingagents.recommendation import DailyRecommender

    if trade_date is None:
        trade_date = datetime.date.today().isoformat()

    manager = get_history_manager()

    # Try to get cached result first (unless refresh=True)
    if not refresh:
        cached = manager.get_result_by_date("daily", trade_date)
        if cached:
            return cached["result"]

    # Generate new recommendation
    recommender = DailyRecommender()
    result = recommender.generate_recommendations(
        trade_date=trade_date,
        max_themes=max_themes,
        max_stocks_per_theme=max_stocks,
        min_amount=min_amount,
        with_deep_analysis=with_analysis,
    )

    # Build response
    response = {
        "trade_date": result["trade_date"],
        "timestamp": result["timestamp"],
        "themes": result["themes"],
        "stocks": result["stocks"],
        "analysis": result.get("analysis", {}),
        "summary": result["summary"],
    }

    # Save to history
    manager.save_result("daily", trade_date, response)

    return response


# ── Weekly Recommendation ──────────────────────────────────────────────────

@router.get("/weekly")
async def recommend_weekly(
    week_start: Optional[str] = Query(None, description="周起始日期 (YYYY-MM-DD)"),
    max_themes: int = Query(5, description="最大主题数量"),
    max_stocks: int = Query(5, description="每个主题最大股票数"),
    min_amount: float = Query(1e8, description="最小成交额（元）"),
    max_analysis: int = Query(0, description="最多分析股票数量（0=不分析，更快）"),
    refresh: bool = Query(False, description="强制重新生成（忽略缓存）"),
):
    """获取每周股票推荐。

    流程：
    1. 汇聚本周财经新闻
    2. LLM提取投资主题
    3. 篛选股票
    4. 可选：运行完整分析

    Args:
        refresh: 若为False，优先返回缓存结果

    Returns:
        Dict with week info, themes, stocks, analysis, summary
    """
    from tradingagents.recommendation import WeeklyRecommender

    if week_start is None:
        today = datetime.date.today()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.isoformat()

    manager = get_history_manager()

    # Try to get cached result first (unless refresh=True)
    if not refresh:
        cached = manager.get_result_by_date("weekly", week_start)
        if cached:
            return cached["result"]

    # Generate new recommendation
    recommender = WeeklyRecommender()
    result = recommender.generate_recommendations(
        week_start=week_start,
        max_themes=max_themes,
        max_stocks_per_theme=max_stocks,
        min_amount=min_amount,
        max_analysis_stocks=max_analysis,
    )

    # Build response
    response = {
        "week_start": result["week_start"],
        "week_end": result["week_end"],
        "themes": result["themes"],
        "stocks": result["stocks"],
        "analysis": result["analysis"],
        "summary": result["summary"],
        "timestamp": result["timestamp"],
    }

    # Save to history
    manager.save_result("weekly", week_start, response)

    return response


# ── Top Gainers ───────────────────────────────────────────────────────────

@router.get("/top")
async def get_top_gainers(
    min_amount: float = Query(1e8, description="最小成交额"),
    top_n: int = Query(20, description="显示数量"),
    refresh: bool = Query(False, description="强制重新获取（忽略缓存）"),
):
    """获取涨幅榜。

    Args:
        refresh: 若为False，优先返回缓存结果

    Returns:
        List of top gaining stocks with score
    """
    from tradingagents.recommendation import StockScreener

    trade_date = datetime.date.today().isoformat()
    manager = get_history_manager()

    # Try to get cached result first (unless refresh=True)
    if not refresh:
        cached = manager.get_result_by_date("top", trade_date)
        if cached:
            return cached["result"]

    # Get fresh data
    screener = StockScreener()
    stocks = screener.get_top_gainers(top_n=top_n)

    # Filter by amount
    results = []
    for _, row in stocks.iterrows():
        amount = row.get("amount", 0) or 0
        if amount >= min_amount:
            results.append({
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "price": row.get("price", 0),
                "change_pct": row.get("change_pct", 0),
                "amount": amount,
                "score": row.get("score", 0),
            })

    response = {
        "trade_date": trade_date,
        "total": len(results),
        "min_amount": min_amount,
        "stocks": results,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Save to history
    manager.save_result("top", trade_date, response)

    return response


# ── Other Endpoints ───────────────────────────────────────────────────────

@router.get("/themes")
async def get_themes(
    trade_date: Optional[str] = Query(None, description="交易日期 (YYYY-MM-DD)"),
    limit: int = Query(50, description="新闻数量上限"),
):
    """仅获取热点主题（不筛选股票）。

    Returns:
        List of theme dicts
    """
    from tradingagents.recommendation import ThemeExtractor

    if trade_date is None:
        trade_date = datetime.date.today().isoformat()

    extractor = ThemeExtractor()
    news = extractor.get_news_from_tushare(limit=limit)
    themes = extractor.extract_themes(news)

    return {
        "trade_date": trade_date,
        "news_count": len(news),
        "themes": themes,
    }


@router.get("/screen")
async def screen_stocks(
    min_change_pct: float = Query(0, description="最小涨幅百分比"),
    max_change_pct: float = Query(15, description="最大涨幅百分比"),
    min_amount: float = Query(1e8, description="最小成交额（元）"),
    top_n: int = Query(50, description="返回数量"),
):
    """篮选股票（按涨幅和成交额）。

    Returns:
        Screened stocks with scoring
    """
    from tradingagents.recommendation import StockScreener

    screener = StockScreener()
    stocks = screener.screen(
        min_change_pct=min_change_pct,
        max_change_pct=max_change_pct,
        min_amount=min_amount,
        top_n=top_n,
    )

    results = []
    for _, row in stocks.iterrows():
        results.append({
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "price": row.get("price", 0),
            "change_pct": row.get("change_pct", 0),
            "amount": row.get("amount", 0) or 0,
            "score": row.get("score", 0),
        })

    return {
        "criteria": {
            "min_change_pct": min_change_pct,
            "max_change_pct": max_change_pct,
            "min_amount": min_amount,
        },
        "total": len(results),
        "stocks": results,
    }