"""API routes for TradingAgents Web UI."""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse, Response

from .models import (
    AnalyzeRequest,
    TaskStatus,
    EventType,
    SSEEvent,
    HistoryResponse,
    SystemConfig,
    TaskDetail,
)
from .task_manager import get_task_manager
from .stream_adapter import start_analysis, get_runner
from .holdings_router import get_holdings_manager
from .holdings_manager import format_holdings_for_prompt
from .config import WEB_CONFIG
from .logging_config import log_analysis_event, log_exception, get_logger

router = APIRouter()
logger = get_logger("tradingagents.web.router")


@router.post("/api/analyze/start")
async def analyze_start(req: AnalyzeRequest):
    """Start a new analysis task."""
    import datetime

    trade_date = req.trade_date or datetime.date.today().isoformat()
    config = {}
    if req.max_debate_rounds is not None:
        config["max_debate_rounds"] = req.max_debate_rounds
    if req.max_risk_discuss_rounds is not None:
        config["max_risk_discuss_rounds"] = req.max_risk_discuss_rounds
    if req.data_vendors:
        config["data_vendors"] = req.data_vendors

    task_id = get_task_manager().create_task(
        ticker=req.ticker,
        trade_date=trade_date,
        config={
            "analysts": req.analysts,
            **config,
        },
    )

    holding = get_holdings_manager().get_holding_by_ticker(req.ticker)
    portfolio_holdings = format_holdings_for_prompt(holding)

    log_analysis_event(
        "api_start_analysis",
        "Submitting analysis task",
        task_id=task_id,
        ticker=req.ticker,
        trade_date=trade_date,
        analysts=req.analysts,
        config=config,
        has_portfolio_holding=holding is not None,
    )

    await start_analysis(
        task_id=task_id,
        ticker=req.ticker,
        trade_date=trade_date,
        analysts=req.analysts,
        config_override=config if config else None,
        portfolio_holdings=portfolio_holdings,
    )

    log_analysis_event(
        "api_start_analysis",
        "Analysis task submitted",
        task_id=task_id,
        ticker=req.ticker,
        trade_date=trade_date,
    )
    return {"task_id": task_id, "status": TaskStatus.RUNNING.value}


@router.get("/api/analyze/{task_id}/status")
async def analyze_status(task_id: str):
    """Get task status."""
    task = get_task_manager().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task["task_id"],
        "ticker": task["ticker"],
        "stock_name": task.get("stock_name"),
        "trade_date": task["trade_date"],
        "status": task["status"],
        "created_at": task["created_at"],
        "completed_at": task.get("completed_at"),
        "error": task.get("error"),
        "signal": task.get("signal"),
    }


@router.post("/api/analyze/{task_id}/cancel")
async def analyze_cancel(task_id: str):
    """Cancel a running analysis task."""
    task = get_task_manager().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check if task is still running
    if task["status"] not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Task is not running")

    # Signal the runner to stop
    runner = get_runner(task_id)
    if runner:
        runner.cancel()
        log_analysis_event(
            "api_cancel_analysis",
            "Analysis runner cancellation requested",
            task_id=task_id,
            ticker=task.get("ticker"),
        )

    # Update task status
    get_task_manager().update_status(task_id, TaskStatus.CANCELLED)

    return {"task_id": task_id, "status": TaskStatus.CANCELLED.value}


@router.get("/api/analyze/{task_id}/result")
async def analyze_result(task_id: str):
    """Get full analysis result."""
    task = get_task_manager().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "ticker": task.get("ticker"),
        "trade_date": task.get("trade_date"),
        "result": task.get("result"),
        "signal": task.get("signal"),
        "error": task.get("error"),
    }


@router.get("/api/analyze/{task_id}/events")
async def analyze_events(task_id: str):
    """SSE stream of analysis events."""
    async def event_stream():
        runner = get_runner(task_id)

        if not runner:
            # Replay historical events from DB
            detail = get_task_manager().get_task_from_db(task_id)
            if detail and detail.events:
                for ev in detail.events:
                    try:
                        event = SSEEvent(
                            type=EventType(ev["type"]),
                            task_id=task_id,
                            data=ev["data"],
                        )
                        yield event.to_sse()
                    except Exception as exc:
                        log_exception(exc, context={
                            "task_id": task_id,
                            "stage": "sse_replay_event",
                            "event": ev,
                        })

            # Send terminal event based on actual task status
            task = get_task_manager().get_task(task_id)
            if task and task["status"] == TaskStatus.COMPLETED.value:
                payload = json.dumps({"task_id": task_id}, ensure_ascii=False)
                yield f"event: {EventType.COMPLETED.value}\ndata: {payload}\n\n"
            elif task and task["status"] == TaskStatus.FAILED.value:
                err = task.get("error") or "分析失败"
                payload = json.dumps({"error": err}, ensure_ascii=False)
                yield f"event: {EventType.FAILED.value}\ndata: {payload}\n\n"
            elif task and task["status"] in (TaskStatus.RUNNING.value, TaskStatus.PENDING.value):
                # Runner lost (server restart) — mark as failed
                get_task_manager().update_status(task_id, TaskStatus.FAILED, error="服务重启，任务中断")
                payload = json.dumps({"error": "服务重启，任务中断"}, ensure_ascii=False)
                yield f"event: {EventType.FAILED.value}\ndata: {payload}\n\n"
            else:
                payload = json.dumps({"task_id": task_id}, ensure_ascii=False)
                yield f"event: {EventType.COMPLETED.value}\ndata: {payload}\n\n"
            return

        while True:
            try:
                event = await asyncio.wait_for(runner.queue.get(), timeout=2.0)
                yield event.to_sse()
                if event.type in (EventType.COMPLETED, EventType.FAILED):
                    break
            except asyncio.TimeoutError:
                yield ":\n\n"
                task = get_task_manager().get_task(task_id)
                if task and task["status"] == TaskStatus.COMPLETED.value:
                    payload = json.dumps({"task_id": task_id}, ensure_ascii=False)
                    yield f"event: {EventType.COMPLETED.value}\ndata: {payload}\n\n"
                    break
                elif task and task["status"] == TaskStatus.FAILED.value:
                    err = task.get("error") or "分析失败"
                    payload = json.dumps({"error": err}, ensure_ascii=False)
                    yield f"event: {EventType.FAILED.value}\ndata: {payload}\n\n"
                    break
                elif task and task["status"] == TaskStatus.CANCELLED.value:
                    payload = json.dumps({"error": "分析已取消"}, ensure_ascii=False)
                    yield f"event: {EventType.FAILED.value}\ndata: {payload}\n\n"
                    break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/history")
async def history_list(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List historical analysis tasks."""
    tasks = get_task_manager().list_tasks(limit=limit, offset=offset)
    total = get_task_manager().get_total_count()
    return HistoryResponse(tasks=tasks, total=total)


@router.get("/api/history/{task_id}")
async def history_detail(task_id: str):
    """Get detailed historical task with events."""
    detail = get_task_manager().get_task_from_db(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Task not found")
    return detail


@router.get("/api/kline/{ticker}")
async def kline_data(ticker: str, days: int = Query(90, ge=10, le=365)):
    """Get K-line (OHLCV) data for a ticker using tradingagents' fallback-enabled data fetch."""
    import datetime
    import asyncio
    import io
    import csv

    def _fetch():
        try:
            from tradingagents.dataflows.akshare_stock import get_stock

            end = datetime.date.today()
            start = end - datetime.timedelta(days=days + 30)  # extra buffer for trading days

            # Use tradingagents' built-in get_stock with fallback mechanism
            csv_data = get_stock(
                symbol=ticker,  # expects format like "600000.SH"
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
            )

            # Parse CSV response
            lines = csv_data.strip().split('\n')
            # Skip header lines (start with #) and empty lines
            data_lines = [l for l in lines if l and not l.startswith('#')]
            if not data_lines:
                return {"error": "No data returned"}

            # Parse CSV
            reader = csv.DictReader(data_lines)
            records = []
            for row in reader:
                # Ensure we have the required fields
                if 'Date' in row and 'Open' in row:
                    records.append({
                        "time": row['Date'][:10],
                        "open": float(row['Open']) if row['Open'] else 0,
                        "high": float(row['High']) if row['High'] else 0,
                        "low": float(row['Low']) if row['Low'] else 0,
                        "close": float(row['Close']) if row['Close'] else 0,
                        "volume": float(row.get('Volume', 0) or 0),
                    })

            # Take only the requested number of days
            records = records[-days:]
            return records
        except Exception as e:
            logger.warning(
                "K-line data fetch failed",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {
                    "ticker": ticker,
                    "days": days,
                    "stage": "kline_fetch",
                }},
            )
            return {"error": str(e)}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _fetch)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"ticker": ticker, "data": result}


@router.get("/api/config")
async def system_config():
    """Get system configuration."""
    from tradingagents.default_config import DEFAULT_CONFIG

    return SystemConfig(
        llm_provider=DEFAULT_CONFIG.get("llm_provider", "minimax"),
        deep_think_llm=DEFAULT_CONFIG.get("deep_think_llm", ""),
        quick_think_llm=DEFAULT_CONFIG.get("quick_think_llm", ""),
        default_analysts=["market", "social", "news", "fundamentals"],
        default_debate_rounds=DEFAULT_CONFIG.get("max_debate_rounds", 3),
        default_risk_rounds=DEFAULT_CONFIG.get("max_risk_discuss_rounds", 2),
    )


@router.get("/health")
async def health_check():
    """Health check endpoint with dependency validation."""
    import os
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

    results = {}
    overall = "healthy"

    def _check_db():
        db_path = WEB_CONFIG["db_path"]
        with sqlite3.connect(db_path, timeout=5) as conn:
            conn.execute("SELECT 1")
        return "ok"

    def _check_tushare():
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            return "missing_token"
        return "ok"

    def _check_akshare():
        try:
            import akshare as ak
            _ = ak.stock_zh_a_spot_em()
            return "ok"
        except Exception as e:
            return f"error: {type(e).__name__}"

    def _check_llm():
        from tradingagents.default_config import DEFAULT_CONFIG
        provider = DEFAULT_CONFIG.get("llm_provider", "minimax")
        key_envs = {
            "minimax": "MINIMAX_API_KEY",
            "alibaba": "DASHSCOPE_API_KEY",
            "aliyun_coding_plan": "ALIYUN_CODING_PLAN_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env = key_envs.get(provider, "")
        if env and os.environ.get(env):
            return "ok"
        # Check fallback envs
        if provider == "alibaba" and os.environ.get("ALIBABA_API_KEY"):
            return "ok"
        if provider == "aliyun_coding_plan" and os.environ.get("CODING_PLAN_API_KEY"):
            return "ok"
        return f"missing_api_key ({env})"

    checks = [
        ("db", _check_db),
        ("tushare", _check_tushare),
        ("akshare", _check_akshare),
        ("llm", _check_llm),
    ]

    for name, check_fn in checks:
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(check_fn)
                result = future.result(timeout=10)
                results[name] = result
        except FutureTimeoutError:
            results[name] = "timeout"
            overall = "degraded"
        except Exception as e:
            logger.warning(
                "Health check dependency failed",
                exc_info=(type(e), e, e.__traceback__),
                extra={"extra_data": {
                    "check": name,
                    "stage": "health_check",
                }},
            )
            results[name] = f"error: {type(e).__name__}: {str(e)}"
            overall = "degraded"

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "checks": results},
    )


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus-style metrics endpoint for monitoring."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.utils.token_tracker import get_all_stats
    from tradingagents.utils.data_cache import get_data_cache
    import os

    lines = []

    # System info
    lines.append(f"tradingagents_version 0.2.1")
    lines.append(f"tradingagents_llm_provider {DEFAULT_CONFIG.get('llm_provider', 'unknown')}")

    # Task manager stats
    tm = get_task_manager()
    total_tasks = tm.get_total_count()
    lines.append(f"tradingagents_tasks_total {total_tasks}")

    # Count by status from database
    import sqlite3
    db_path = WEB_CONFIG["db_path"]
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall()
            for row in rows:
                lines.append(f"tradingagents_tasks_by_status{{status=\"{row['status']}\"}} {row['cnt']}")
    except Exception as exc:
        log_exception(exc, context={"stage": "metrics_task_status_counts"})

    # Token usage stats
    token_stats = get_all_stats()
    total_input = sum(s.get("total_input_tokens", 0) for s in token_stats.values())
    total_output = sum(s.get("total_output_tokens", 0) for s in token_stats.values())
    lines.append(f"tradingagents_tokens_input_total {total_input}")
    lines.append(f"tradingagents_tokens_output_total {total_output}")

    # Active tasks
    from .stream_adapter import _active_tasks, _task_semaphore
    active_count = len(_active_tasks)
    semaphore_value = _task_semaphore._value if hasattr(_task_semaphore, '_value') else 0
    max_concurrent = DEFAULT_CONFIG.get("max_concurrent_tasks", 4)
    lines.append(f"tradingagents_tasks_active {active_count}")
    lines.append(f"tradingagents_semaphore_available {semaphore_value}")
    lines.append(f"tradingagents_max_concurrent {max_concurrent}")

    # Cache stats
    try:
        cache = get_data_cache()
        cache_files = list(cache._cache_dir.glob("*.json"))
        lines.append(f"tradingagents_cache_entries {len(cache_files)}")
    except Exception as exc:
        log_exception(exc, context={"stage": "metrics_cache_stats"})

    # Data source availability
    tushare_token = os.environ.get("TUSHARE_TOKEN", "")
    lines.append(f"tradingagents_tushare_available {1 if tushare_token else 0}")

    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain",
    )
