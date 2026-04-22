"""API routes for TradingAgents Web UI."""
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

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
from .config import WEB_CONFIG

router = APIRouter()


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

    await start_analysis(
        task_id=task_id,
        ticker=req.ticker,
        trade_date=trade_date,
        analysts=req.analysts,
        config_override=config if config else None,
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
        "trade_date": task["trade_date"],
        "status": task["status"],
        "created_at": task["created_at"],
        "completed_at": task.get("completed_at"),
        "error": task.get("error"),
        "signal": task.get("signal"),
    }


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
                    except Exception:
                        pass

            # Send terminal event based on actual task status
            task = get_task_manager().get_task(task_id)
            if task and task["status"] == TaskStatus.COMPLETED.value:
                yield f"event: {EventType.COMPLETED.value}\ndata: {{\"task_id\": \"{task_id}\"}}\n\n"
            elif task and task["status"] == TaskStatus.FAILED.value:
                err = task.get("error") or "分析失败"
                yield f"event: {EventType.FAILED.value}\ndata: {{\"error\": \"{err}\"}}\n\n"
            elif task and task["status"] in (TaskStatus.RUNNING.value, TaskStatus.PENDING.value):
                # Runner lost (server restart) — mark as failed
                get_task_manager().update_status(task_id, TaskStatus.FAILED, error="服务重启，任务中断")
                yield f"event: {EventType.FAILED.value}\ndata: {{\"error\": \"服务重启，任务中断\"}}\n\n"
            else:
                yield f"event: {EventType.COMPLETED.value}\ndata: {{\"task_id\": \"{task_id}\"}}\n\n"
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
                if task and task["status"] in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
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
    """Get K-line (OHLCV) data for a ticker via akshare."""
    import datetime
    import asyncio

    def _fetch():
        try:
            import akshare as ak
            import pandas as pd

            end = datetime.date.today()
            start = end - datetime.timedelta(days=days + 30)  # extra buffer for trading days

            # Normalize ticker: strip exchange suffix for akshare
            symbol = ticker.split(".")[0]

            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq",
            )
            # Rename columns
            df = df.rename(columns={
                "日期": "date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume",
            })
            df = df[["date", "open", "high", "low", "close", "volume"]].tail(days)
            records = []
            for _, row in df.iterrows():
                records.append({
                    "time": str(row["date"])[:10],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                })
            return records
        except Exception as e:
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
