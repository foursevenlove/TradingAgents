#!/bin/bash
# TradingAgents 服务器部署脚本
# 用法: ./scripts/deploy_server.sh [版本号]
# 示例: ./scripts/deploy_server.sh v0.2.1

set -e

# ===== 配置区域 =====
# 阿里云镜像仓库配置
ALIYUN_REGISTRY="registry.cn-shanghai.aliyuncs.com"
ALIYUN_NAMESPACE="foursevenlove"
IMAGE_NAME="tradingagents"

# ===== 参数解析 =====
VERSION="${1:-latest}"
FULL_IMAGE="${ALIYUN_REGISTRY}/${ALIYUN_NAMESPACE}/${IMAGE_NAME}:${VERSION}"

# ===== 颜色输出 =====
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  TradingAgents 服务器部署${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# ===== 检查 Docker =====
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    exit 1
fi

# ===== 检查阿里云登录 =====
echo -e "${YELLOW}检查阿里云镜像仓库登录状态...${NC}"
# 检查 docker config.json 中是否有对应 registry 的认证
if grep -q "${ALIYUN_REGISTRY}" ~/.docker/config.json 2>/dev/null; then
    echo -e "${GREEN}✓ 已登录阿里云镜像仓库${NC}"
else
    echo -e "${YELLOW}需要登录阿里云镜像仓库${NC}"
    echo -e "${YELLOW}请执行: docker login ${ALIYUN_REGISTRY}${NC}"
    read -p "是否现在登录? (y/n): " do_login
    if [[ "$do_login" == "y" ]]; then
        docker login ${ALIYUN_REGISTRY}
    else
        echo -e "${RED}未登录，退出${NC}"
        exit 1
    fi
fi
echo ""

# ===== 检查环境变量文件 =====
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告: .env 文件不存在${NC}"
    echo -e "${YELLOW}请创建 .env 文件配置以下内容:${NC}"
    echo ""
    echo "  TUSHARE_TOKEN=your_tushare_token"
    echo "  MINIMAX_API_KEY=your_minimax_key"
    echo "  TRADINGAGENTS_PORT=8000"
    echo "  TRADINGAGENTS_CORS_ORIGINS=https://your-domain.com"
    echo ""
    read -p "是否继续部署? (y/n): " continue_deploy
    if [[ "$continue_deploy" != "y" ]]; then
        exit 1
    fi
fi

# ===== 拉取镜像 =====
echo -e "${YELLOW}拉取镜像: ${FULL_IMAGE}${NC}"
docker pull "${FULL_IMAGE}"
echo -e "${GREEN}✓ 镜像拉取完成${NC}"
echo ""

# ===== 停止旧容器 =====
echo -e "${YELLOW}停止旧服务...${NC}"
docker-compose -f docker-compose.prod.yaml down 2>/dev/null || true
echo -e "${GREEN}✓ 旧服务已停止${NC}"
echo ""

# ===== 启动新服务 =====
echo -e "${YELLOW}启动新服务...${NC}"
docker-compose -f docker-compose.prod.yaml up -d
echo -e "${GREEN}✓ 服务已启动${NC}"
echo ""

# ===== 等待健康检查 =====
echo -e "${YELLOW}等待健康检查...${NC}"
sleep 10

# ===== 检查服务状态 =====
echo -e "${YELLOW}检查服务状态...${NC}"
CONTAINER_NAME="tradingagents-web"
CONTAINER_STATUS=$(docker inspect --format='{{.State.Health.Status}}' ${CONTAINER_NAME} 2>/dev/null || echo "unknown")

if [ "${CONTAINER_STATUS}" == "healthy" ]; then
    echo -e "${GREEN}✓ 服务健康${NC}"
elif [ "${CONTAINER_STATUS}" == "starting" ]; then
    echo -e "${YELLOW}⚠ 服务正在启动，请稍后检查${NC}"
else
    echo -e "${RED}✗ 服务状态异常: ${CONTAINER_STATUS}${NC}"
    echo -e "${YELLOW}查看日志:${NC}"
    docker logs --tail 50 ${CONTAINER_NAME}
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  部署完成！${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "服务地址:"
echo -e "  ${GREEN}http://localhost:${TRADINGAGENTS_PORT:-8000}${NC}"
echo ""
echo -e "健康检查:"
echo -e "  curl http://localhost:${TRADINGAGENTS_PORT:-8000}/health"
echo ""
echo -e "查看日志:"
echo -e "  docker-compose -f docker-compose.prod.yaml logs -f"
echo ""
echo -e "停止服务:"
echo -e "  docker-compose -f docker-compose.prod.yaml down"