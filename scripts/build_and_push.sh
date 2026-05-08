#!/bin/bash
# TradingAgents 镜像构建与推送脚本
# 用法: ./scripts/build_and_push.sh [版本号]
# 示例: ./scripts/build_and_push.sh v0.2.1

set -e

# ===== 配置区域 =====
# 阿里云镜像仓库配置
ALIYUN_REGISTRY="registry.cn-shanghai.aliyuncs.com"
ALIYUN_NAMESPACE="foursevenlove"
IMAGE_NAME="tradingagents"

# ===== 参数解析 =====
VERSION="${1:-latest}"
BRANCH=$(git branch --show-current)
COMMIT_SHA=$(git rev-parse --short HEAD)

# 构建完整镜像标签
FULL_IMAGE="${ALIYUN_REGISTRY}/${ALIYUN_NAMESPACE}/${IMAGE_NAME}"
IMAGE_TAG="${FULL_IMAGE}:${VERSION}"
IMAGE_TAG_COMMIT="${FULL_IMAGE}:${COMMIT_SHA}"
IMAGE_TAG_BRANCH="${FULL_IMAGE}:${BRANCH}"

# ===== 颜色输出 =====
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  TradingAgents 镜像构建与推送${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# ===== 检查 Docker =====
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
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
    echo -e "${YELLOW}用户名: 你的阿里云账号全名${NC}"
    echo -e "${YELLOW}密码: 在阿里云控制台设置的镜像仓库密码${NC}"
    read -p "是否现在登录? (y/n): " do_login
    if [[ "$do_login" == "y" ]]; then
        docker login ${ALIYUN_REGISTRY}
    else
        echo -e "${RED}未登录，退出${NC}"
        exit 1
    fi
fi
echo ""

# ===== 构建镜像 =====
echo -e "${YELLOW}构建 Docker 镜像...${NC}"
echo -e "  版本: ${VERSION}"
echo -e "  分支: ${BRANCH}"
echo -e "  Commit: ${COMMIT_SHA}"
echo ""

docker build \
    -t "${IMAGE_TAG}" \
    -t "${IMAGE_TAG_COMMIT}" \
    -t "${IMAGE_TAG_BRANCH}" \
    -t "${FULL_IMAGE}:latest" \
    --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
    --build-arg VERSION=${VERSION} \
    --build-arg COMMIT_SHA=${COMMIT_SHA} \
    .

echo -e "${GREEN}✓ 镜像构建完成${NC}"
echo ""

# ===== 推送镜像 =====
echo -e "${YELLOW}推送镜像到阿里云...${NC}"

# 推送版本标签
docker push "${IMAGE_TAG}"
echo -e "${GREEN}  ✓ ${IMAGE_TAG}${NC}"

# 推送 commit 标签
docker push "${IMAGE_TAG_COMMIT}"
echo -e "${GREEN}  ✓ ${IMAGE_TAG_COMMIT}${NC}"

# 推送分支标签
docker push "${IMAGE_TAG_BRANCH}"
echo -e "${GREEN}  ✓ ${IMAGE_TAG_BRANCH}${NC}"

# 推送 latest 标签
docker push "${FULL_IMAGE}:latest"
echo -e "${GREEN}  ✓ ${FULL_IMAGE}:latest${NC}"

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  推送完成！${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "镜像地址:"
echo -e "  ${BLUE}${IMAGE_TAG}${NC}"
echo -e "  ${BLUE}${IMAGE_TAG_COMMIT}${NC}"
echo -e "  ${BLUE}${IMAGE_TAG_BRANCH}${NC}"
echo -e "  ${BLUE}${FULL_IMAGE}:latest${NC}"
echo ""
echo -e "服务器部署命令:"
echo -e "  ${YELLOW}docker pull ${IMAGE_TAG}${NC}"
echo -e "  或"
echo -e "  ${YELLOW}docker-compose -f docker-compose.prod.yaml up -d${NC}"