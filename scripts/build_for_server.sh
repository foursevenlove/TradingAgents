#!/bin/bash
# Mac 上构建 Ubuntu 服务器可用镜像并推送到阿里云
# 用法: ./scripts/build_for_server.sh [版本号]

set -e

# ===== 配置 =====
ALIYUN_REGISTRY="registry.cn-shanghai.aliyuncs.com"
ALIYUN_NAMESPACE="foursevenlove"
IMAGE_NAME="tradingagents"
TARGET_PLATFORM="linux/amd64"

# ===== 参数 =====
VERSION="${1:-latest}"
COMMIT_SHA=$(git rev-parse --short HEAD)
BRANCH=$(git branch --show-current)

FULL_IMAGE="${ALIYUN_REGISTRY}/${ALIYUN_NAMESPACE}/${IMAGE_NAME}"

# ===== 颜色 =====
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Mac → Ubuntu 镜像构建${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "目标平台: ${TARGET_PLATFORM}"
echo -e "版本: ${VERSION}"
echo -e "Commit: ${COMMIT_SHA}"
echo ""

# ===== 检查登录 =====
if ! grep -q "${ALIYUN_REGISTRY}" ~/.docker/config.json 2>/dev/null; then
    echo -e "${RED}请先登录: docker login ${ALIYUN_REGISTRY}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 已登录阿里云${NC}"

# ===== 构建并推送（直接推送，不存本地）=====
echo -e "${YELLOW}开始构建 amd64 镜像...${NC}"
echo -e "${YELLOW}（跨平台构建需要几分钟，请耐心等待）${NC}"

# Docker buildx 需要使用 host.docker.internal 访问宿主机代理
docker buildx build \
    --platform ${TARGET_PLATFORM} \
    -f Dockerfile.simple \
    --build-arg http_proxy=http://host.docker.internal:7890 \
    --build-arg https_proxy=http://host.docker.internal:7890 \
    -t "${FULL_IMAGE}:${VERSION}" \
    -t "${FULL_IMAGE}:${COMMIT_SHA}" \
    -t "${FULL_IMAGE}:latest" \
    --push \
    .

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  构建推送完成！${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "镜像地址:"
echo -e "  ${BLUE}${FULL_IMAGE}:${VERSION}${NC}"
echo -e "  ${BLUE}${FULL_IMAGE}:${COMMIT_SHA}${NC}"
echo -e "  ${BLUE}${FULL_IMAGE}:latest${NC}"
echo ""
echo -e "服务器部署:"
echo -e "  ${YELLOW}docker pull ${FULL_IMAGE}:${VERSION}${NC}"
echo -e "  ${YELLOW}docker-compose -f docker-compose.prod.yaml up -d${NC}"