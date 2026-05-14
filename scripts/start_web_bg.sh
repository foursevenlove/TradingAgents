#!/bin/bash
# 后台启动 TradingAgents Web UI
#   logs/web.log              — uvicorn HTTP 访问日志
#   logs/agent_<id>_*.log     — 每次分析独立的 Agent 日志

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ── 加载环境变量 ──────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "加载 .env 环境变量..."
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep -v '^$' | xargs)
fi

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

WEB_LOG="$LOG_DIR/web.log"
PID_FILE="$LOG_DIR/web.pid"

# ── 停止已有实例 ──────────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "停止旧实例 (PID $OLD_PID)..."
        kill "$OLD_PID"
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# ── 构建前端 ──────────────────────────────────────────────────
if [ ! -d "web/frontend/node_modules" ]; then
    echo "安装前端依赖..."
    cd web/frontend && npm install && cd "$PROJECT_ROOT"
fi

echo "构建前端..."
cd web/frontend && npm run build 2>&1 | grep -E "(built|error|warn)" && cd "$PROJECT_ROOT"

# ── 启动后端（后台） ──────────────────────────────────────────
echo "后台启动 FastAPI 服务..."
echo "  服务日志  → $WEB_LOG"
echo "  Agent日志 → $LOG_DIR/agent_<id>_<ticker>_<date>.log  (每次分析独立文件)"

# 直接用 nohup 启动 uvicorn，stderr/stdout 都写到 web.log
# Agent 分析日志由 stream_adapter.py 直接写入 logs/agent_*.log
# 直接用 conda 环境里的 uvicorn，避免用到系统 Python
UVICORN="/usr/local/anaconda3/envs/tradingagents/bin/uvicorn"
if [ ! -f "$UVICORN" ]; then
    # fallback: try conda run
    UVICORN="conda run -n tradingagents uvicorn"
fi

nohup $UVICORN web.backend.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    >> "$WEB_LOG" 2>&1 &

echo $! > "$PID_FILE"
ACTUAL_PID=$!

# 等待服务就绪
echo -n "等待服务启动"
for i in $(seq 1 20); do
    sleep 1
    echo -n "."
    if curl -s http://localhost:8000/api/config > /dev/null 2>&1; then
        echo ""
        echo "✅ 服务已启动 (PID $ACTUAL_PID)"
        echo "   访问地址: http://localhost:8000"
        echo ""
        echo "实时查看日志:"
        echo "  tail -f $WEB_LOG"
        echo "  tail -f $LOG_DIR/agent_*.log   # 分析过程日志（每次分析独立文件）"
        echo ""
        echo "停止服务:"
        echo "  ./scripts/stop_web.sh"
        exit 0
    fi
done

echo ""
echo "⚠️  服务启动超时，请检查日志:"
tail -20 "$WEB_LOG"
exit 1
