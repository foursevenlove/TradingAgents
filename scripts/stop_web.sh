#!/bin/bash
# 停止后台运行的 TradingAgents Web UI

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/logs/web.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "未找到 PID 文件，尝试按端口停止..."
    PIDS=$(lsof -ti:8000 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "停止端口 8000 上的进程: $PIDS"
        echo "$PIDS" | xargs kill
        sleep 1
        echo "✅ 已停止"
    else
        echo "端口 8000 上没有运行中的服务"
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    echo "停止服务 (PID $PID)..."
    kill "$PID"
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID"
    fi
    echo "✅ 已停止"
else
    echo "进程 $PID 已不存在"
fi

rm -f "$PID_FILE"
