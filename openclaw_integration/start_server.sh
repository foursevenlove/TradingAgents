#!/bin/bash
# TradingAgents API Server 启动脚本

# 设置工作目录
cd "$(dirname "$0")/.."

# 检查环境变量
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  警告: 未设置 TELEGRAM_BOT_TOKEN 环境变量"
    echo "   请运行: export TELEGRAM_BOT_TOKEN='your_token'"
fi

if [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "⚠️  警告: 未设置 TELEGRAM_CHAT_ID 环境变量"
    echo "   请运行: export TELEGRAM_CHAT_ID='your_chat_id'"
fi

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import flask" 2>/dev/null || {
    echo "❌ 缺少 flask，正在安装..."
    pip install flask
}

python3 -c "import requests" 2>/dev/null || {
    echo "❌ 缺少 requests，正在安装..."
    pip install requests
}

# 启动服务
echo "🚀 启动 TradingAgents API Server..."
python3 openclaw_integration/api_server.py
