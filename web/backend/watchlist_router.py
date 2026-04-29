"""API routes for watchlist, schedule, and batch analysis."""
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .watchlist_manager import WatchlistManager
from .scheduler_service import get_scheduler, create_scheduler
from .stock_service import search_stocks

router = APIRouter()

# Global watchlist manager instance (created in app.py lifespan)
_wm: Optional[WatchlistManager] = None


def get_watchlist_manager() -> WatchlistManager:
    global _wm
    if _wm is None:
        _wm = WatchlistManager()
    return _wm


def init_watchlist_manager() -> WatchlistManager:
    """Initialize watchlist manager (called from app lifespan)."""
    global _wm
    _wm = WatchlistManager()
    return _wm


# ── Request/Response Models ──────────────────────────────────────────

class StockSearchResult(BaseModel):
    ticker: str
    code: str
    name: str


class AddStockRequest(BaseModel):
    ticker: str = Field(..., description="股票代码，如 600000.SH")
    name: str = Field("", description="股票名称（可选）")


class UpdateStockRequest(BaseModel):
    enabled: bool = Field(..., description="是否启用")


class ScheduleUpdateRequest(BaseModel):
    enabled: bool = Field(..., description="是否启用定时")
    cron_expression: str = Field("0 9 * * *", description="Cron 表达式")
    max_concurrency: int = Field(2, ge=1, le=5, description="最大并发数")
    config: dict = Field(default_factory=dict, description="分析配置覆盖")


class WatchlistItem(BaseModel):
    id: int
    ticker: str
    name: str
    enabled: bool
    created_at: str
    updated_at: str


class BatchRunSummary(BaseModel):
    batch_id: str
    triggered_at: str
    triggered_by: str
    status: str
    total_stocks: int
    completed_count: int
    failed_count: int
    completed_at: Optional[str] = None
    error: Optional[str] = None


class BatchRunDetail(BatchRunSummary):
    tasks: list = Field(default_factory=list)


# ── Watchlist Routes ────────────────────────────────────────────────

@router.get("/api/stocks/search", response_model=List[StockSearchResult])
async def search_stocks_api(
    query: str = Query(..., description="搜索关键词（代码或名称）"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
):
    """Search stocks by code or name."""
    results = search_stocks(query, limit)
    return [StockSearchResult(**r) for r in results]


@router.get("/api/watchlist", response_model=list)
async def list_watchlist(enabled_only: bool = Query(False)):
    """Get watchlist stocks."""
    wm = get_watchlist_manager()
    return wm.list_stocks(enabled_only=enabled_only)


@router.post("/api/watchlist")
async def add_stock(req: AddStockRequest):
    """Add a stock to watchlist."""
    wm = get_watchlist_manager()
    return wm.add_stock(req.ticker, req.name)


@router.delete("/api/watchlist/{stock_id}")
async def remove_stock(stock_id: int):
    """Remove a stock from watchlist."""
    wm = get_watchlist_manager()
    if not wm.remove_stock(stock_id):
        raise HTTPException(status_code=404, detail="Stock not found")
    return {"ok": True}


@router.put("/api/watchlist/{stock_id}")
async def update_stock(stock_id: int, req: UpdateStockRequest):
    """Enable/disable a watchlist stock."""
    wm = get_watchlist_manager()
    if not wm.update_stock(stock_id, req.enabled):
        raise HTTPException(status_code=404, detail="Stock not found")
    return {"ok": True}


# ── Schedule Routes ─────────────────────────────────────────────────

@router.get("/api/schedule")
async def get_schedule():
    """Get schedule configuration."""
    wm = get_watchlist_manager()
    return wm.get_schedule()


@router.put("/api/schedule")
async def update_schedule(req: ScheduleUpdateRequest):
    """Update schedule configuration."""
    from croniter import croniter
    try:
        croniter(req.cron_expression)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")

    wm = get_watchlist_manager()
    schedule = wm.update_schedule(
        enabled=req.enabled,
        cron_expression=req.cron_expression,
        max_concurrency=req.max_concurrency,
        config=req.config,
    )

    # Restart scheduler if running
    scheduler = get_scheduler()
    if scheduler:
        # Calculate next run
        if req.enabled:
            from datetime import datetime
            cr = croniter(req.cron_expression, datetime.now())
            next_run = cr.get_next(datetime)
            wm.update_schedule_next_run(next_run.isoformat())

    return schedule


@router.get("/api/scheduler/status")
async def scheduler_status():
    """Get scheduler status."""
    scheduler = get_scheduler()
    if not scheduler:
        return {"running": False, "enabled": False}
    return scheduler.get_status()


# ── Batch Analysis Routes ───────────────────────────────────────────

@router.post("/api/batch/start")
async def batch_start():
    """Manually trigger batch analysis on all enabled watchlist stocks."""
    wm = get_watchlist_manager()
    stocks = wm.list_stocks(enabled_only=True)
    if not stocks:
        raise HTTPException(status_code=400, detail="自选股列表为空，请先添加自选股")

    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    batch_id = await scheduler.run_batch(triggered_by="manual")
    return {"batch_id": batch_id, "total_stocks": len(stocks)}


@router.get("/api/batch/runs", response_model=list)
async def list_batch_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List batch run history."""
    wm = get_watchlist_manager()
    return wm.list_batch_runs(limit=limit, offset=offset)


@router.get("/api/batch/runs/{batch_id}")
async def get_batch_run(batch_id: str):
    """Get batch run details with per-stock status."""
    wm = get_watchlist_manager()
    batch = wm.get_batch_run(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch run not found")

    tasks = wm.get_batch_tasks(batch_id)

    # Get skipped stocks (stocks that were skipped due to existing analysis)
    trade_date = batch.get("triggered_at", "")
    if trade_date:
        # Extract date from triggered_at timestamp
        trade_date = trade_date[:10]  # "2026-04-26T..." -> "2026-04-26"
    skipped = wm.get_skipped_stocks(batch_id, trade_date)

    return {**batch, "tasks": tasks, "skipped": skipped}
