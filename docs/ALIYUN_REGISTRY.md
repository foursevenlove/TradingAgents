# 阿里云镜像仓库配置指南

## 当前配置

本项目使用以下镜像仓库配置：

- **命名空间**: `foursevenlove`
- **仓库地址**: `registry.cn-shanghai.aliyuncs.com/foursevenlove/tradingagents`
- **区域**: 华东2（上海）

---

## 1. 登录阿里云镜像仓库

```bash
docker login registry.cn-shanghai.aliyuncs.com
```

- **用户名**: 你的阿里云账号全名
- **密码**: 在阿里云控制台设置的 Registry 登录密码

登录状态检查：
```bash
docker login registry.cn-shanghai.aliyuncs.com --get-login
```

---

## 2. 本地构建与推送

```bash
# 1. 登录阿里云镜像仓库
docker login registry.cn-shanghai.aliyuncs.com

# 2. 构建并推送镜像（指定版本号）
./scripts/build_and_push.sh v0.2.1

# 或使用默认 latest 标签
./scripts/build_and_push.sh
```

脚本会自动创建多个标签便于版本管理：
- `v0.2.1` - 指定版本号
- `abc1234` - Git commit SHA（短）
- `dev-claude-cn` - Git 分支名
- `latest` - 最新版本

---

## 3. 服务器部署

将以下文件上传到服务器：
- `docker-compose.prod.yaml`
- `scripts/deploy_server.sh`
- `.env`（配置好 API Keys）

```bash
# 1. 登录阿里云镜像仓库
docker login registry.cn-shanghai.aliyuncs.com

# 2. 执行部署脚本
./scripts/deploy_server.sh v0.2.1

# 或部署最新版本
./scripts/deploy_server.sh
```

部署指定版本：
```bash
./scripts/deploy_server.sh v0.2.1      # 特定版本
./scripts/deploy_server.sh abc1234     # 特定 commit
./scripts/deploy_server.sh dev-claude-cn  # 特定分支
```

---

## 4. 常见问题

### Q: 推送失败提示 "unauthorized"

检查登录状态：
```bash
docker login registry.cn-shanghai.aliyuncs.com
```

确保用户名是完整的阿里云账号（带 @），密码是 Registry 登录密码。

### Q: 服务器拉取慢

确保服务器和镜像仓库在同一区域。华东服务器使用上海镜像仓库速度最快。

### Q: 如何查看可用镜像版本

阿里云控制台 → 容器镜像服务 → 镜像仓库 → `foursevenlove/tradingagents` → 镜像版本

### Q: 如何清理旧镜像

本地清理：
```bash
docker image prune -f
```

阿里云控制台可以手动删除不需要的镜像版本。

---

## 5. 安全建议

1. **不要在脚本中硬编码密码**，每次部署前手动登录
2. **不要推送敏感配置**（API Keys），只推送代码镜像，配置通过 `.env` 注入
3. **生产环境使用固定版本号**，不要用 `latest`（便于回滚）
4. **定期清理旧镜像版本**，节省存储空间