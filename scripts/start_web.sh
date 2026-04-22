#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== TradingAgents Web UI 启动脚本 ==="

# Install Python dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip install -e ".[web]" || pip install fastapi uvicorn
fi

# Install frontend dependencies if needed
if [ ! -d "web/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd web/frontend
    if command -v npm &> /dev/null; then
        npm install
    else
        echo "Warning: npm not found. Frontend will not be built."
    fi
    cd "$PROJECT_ROOT"
fi

# Build frontend
echo "Building frontend..."
cd web/frontend
if command -v npm &> /dev/null; then
    npm run build
fi
cd "$PROJECT_ROOT"

# Start backend (serves static files too)
echo "Starting FastAPI server on http://localhost:8000"
uvicorn web.backend.app:app --host 0.0.0.0 --port 8000 --reload
