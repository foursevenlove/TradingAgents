"""FastAPI entry point for TradingAgents Web UI."""
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .router import router
from .config import WEB_CONFIG
from .watchlist_router import router as watchlist_router, init_watchlist_manager
from .scheduler_service import create_scheduler, get_scheduler
from .exceptions import TradingAgentsError, classify_exception, ErrorResponse
from .logging_config import setup_logging, get_server_logger, log_exception, log_api_request

# Load environment variables from .env file (same as CLI)
load_dotenv()

# Setup logging
setup_logging(
    log_dir=WEB_CONFIG.get("log_dir", "logs"),
    log_level=WEB_CONFIG.get("log_level", "INFO"),
)
_logger = get_server_logger()


def _cleanup_orphan_tasks():
    """Mark running/pending tasks as failed on startup (they lost their runner)."""
    db_path = Path(WEB_CONFIG["db_path"])
    if not db_path.exists():
        return
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """UPDATE tasks SET status = 'failed', error = '服务重启，任务中断'
               WHERE status IN ('running', 'pending')"""
        )
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize scheduler on startup, cleanup on shutdown."""
    # Startup
    _cleanup_orphan_tasks()

    wm = init_watchlist_manager()
    wm.recover_running_batches()

    scheduler = create_scheduler(wm)
    await scheduler.start()

    yield

    # Shutdown
    await scheduler.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TradingAgents Web UI",
        description="Web interface for multi-agent LLM financial trading analysis",
        version="0.2.1",
        lifespan=lifespan,
    )

    # ── Global Exception Handlers ──────────────────────────────────────────────
    @app.exception_handler(TradingAgentsError)
    async def tradingagents_error_handler(request: Request, exc: TradingAgentsError):
        """Handle TradingAgents-specific errors with user-friendly messages."""
        response = exc.to_response()
        log_exception(exc, context={
            "path": request.url.path,
            "method": request.method,
            "error_code": response.error_code,
        })
        return JSONResponse(
            status_code=response.status_code,
            content=response.to_dict(),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle any uncaught exception - service stays alive, user gets friendly message."""
        classified = classify_exception(exc)
        response = classified.to_response()
        log_exception(exc, context={
            "path": request.url.path,
            "method": request.method,
            "error_code": response.error_code,
            "original_type": type(exc).__name__,
        })
        _logger.critical(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
        return JSONResponse(
            status_code=response.status_code,
            content=response.to_dict(),
        )

    # ── Request Logging Middleware ──────────────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        try:
            response: Response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            log_api_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            classified = classify_exception(exc)
            log_api_request(
                method=request.method,
                path=request.url.path,
                status_code=classified.status_code,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise  # Let exception handler deal with it

    # ── CORS Middleware ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(router)
    app.include_router(watchlist_router)

    # Serve frontend static files if built
    frontend_dist = Path(WEB_CONFIG["frontend_dist"])
    if frontend_dist.exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{path:path}")
        async def spa_fallback(request: Request, path: str):
            index_file = frontend_dist / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return {"error": "Frontend not built"}
    else:
        @app.get("/")
        async def root():
            return {
                "message": "TradingAgents Web UI API is running",
                "frontend_status": "not built",
                "docs": "/docs",
            }

    return app


app = create_app()
