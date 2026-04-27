#!/bin/bash
# TradingAgents Ubuntu 启动脚本
# 直接使用 python3 + pip，无需 Docker/conda

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查 Python 和 venv
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装，请先安装: sudo apt install python3 python3-pip python3-venv"
        exit 1
    fi

    # Ubuntu 23.04+ 需要确保 python3-venv 已安装
    if ! python3 -c "import venv" 2>/dev/null; then
        log_error "python3-venv 未安装，请执行: sudo apt install python3-venv"
        exit 1
    fi

    log_info "Python3: $(python3 --version)"
}

# 检查 Node.js（用于前端构建）
check_node() {
    if ! command -v node &> /dev/null; then
        log_warn "Node.js 未安装，跳过前端构建"
        log_warn "如需 Web UI，请安装: sudo apt install nodejs npm"
        return 1
    fi
    log_info "Node.js: $(node --version)"
    return 0
}

# 安装 Python 依赖
install_python_deps() {
    log_info "安装 Python 依赖..."

    # 创建虚拟环境（Ubuntu 23.04+ 必须）
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_info "创建虚拟环境: venv/"
    fi

    # 直接使用 venv 的 pip（不依赖 activate）
    VENV_PIP="./venv/bin/pip"
    VENV_PYTHON="./venv/bin/python"

    # 安装依赖
    $VENV_PIP install --upgrade pip
    $VENV_PIP install -r requirements.txt
    $VENV_PIP install -e .

    log_info "Python 依赖安装完成"
    log_info "使用: ./venv/bin/python 或 source venv/bin/activate"
}

# 构建前端
build_frontend() {
    if ! check_node; then
        return
    fi

    log_info "构建前端..."

    cd web/frontend

    # 安装依赖
    if [ ! -d "node_modules" ]; then
        npm install
    fi

    # 构建
    npm run build

    cd "$SCRIPT_DIR"
    log_info "前端构建完成: web/frontend/dist/"
}

# 启动服务
start_service() {
    log_info "启动 TradingAgents Web 服务..."

    # 检查 venv
    if [ ! -d "venv" ]; then
        log_error "虚拟环境不存在，请先运行: ./start_ubuntu.sh install"
        exit 1
    fi

    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        log_warn ".env 文件不存在，请配置 API Keys"
        log_warn "可复制: cp .env.example .env"
    fi

    # 创建必要目录
    mkdir -p logs reports results

    # 启动参数
    HOST="${TRADINGAGENTS_WEB_HOST:-0.0.0.0}"
    PORT="${TRADINGAGENTS_WEB_PORT:-8000}"

    log_info "服务地址: http://localhost:${PORT}"
    log_info "API 文档: http://localhost:${PORT}/docs"
    log_info "按 Ctrl+C 停止服务"

    # 直接使用 venv 的 uvicorn 启动
    ./venv/bin/uvicorn web.backend.app:app --host "$HOST" --port "$PORT"
}

# 停止服务
stop_service() {
    log_info "停止服务..."
    pkill -f "uvicorn web.backend.app:app" || true
    log_info "服务已停止"
}

# 帮助信息
show_help() {
    echo "TradingAgents Ubuntu 启动脚本"
    echo ""
    echo "用法: ./start_ubuntu.sh [命令]"
    echo ""
    echo "命令:"
    echo "  install   安装依赖（Python venv + pip）"
    echo "  build     构建前端"
    echo "  start     启动 Web 服务"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  all       安装 + 构建 + 启动（首次部署）"
    echo "  help      显示帮助信息"
    echo ""
    echo "Ubuntu 23.04+ 系统依赖:"
    echo "  sudo apt install python3 python3-pip python3-venv nodejs npm"
    echo ""
    echo "环境变量:"
    echo "  TRADINGAGENTS_WEB_HOST  服务地址 (默认: 0.0.0.0)"
    echo "  TRADINGAGENTS_WEB_PORT  服务端口 (默认: 8000)"
}

# 主入口
main() {
    case "${1:-help}" in
        install)
            check_python
            install_python_deps
            ;;
        build)
            build_frontend
            ;;
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            stop_service
            sleep 2
            start_service
            ;;
        all)
            check_python
            install_python_deps
            build_frontend
            start_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"