"""FastAPI entry point for TradingAgents Web UI."""
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .router import router
from .config import WEB_CONFIG
from .watchlist_router import router as watchlist_router, init_watchlist_manager
from .scheduler_service import create_scheduler, get_scheduler

# Load environment variables from .env file (same as CLI)
load_dotenv()


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
