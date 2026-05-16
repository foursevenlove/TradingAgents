# TradingAgents 生产部署指南

## 目录

1. [环境要求](#环境要求)
2. [配置清单](#配置清单)
3. [Docker 部署](#docker-部署)
4. [资源建议](#资源建议)
5. [监控指标](#监控指标)
6. [常见问题](#常见问题)

---

## 环境要求

### 系统要求
- Docker 20.10+
- Docker Compose 2.0+
- 最低 2 核 CPU，4GB 内存
- 建议 4 核 CPU，8GB 内存（生产环境）

### 必需的外部服务
- Tushare Pro 账号 + Token（A股数据）
- LLM Provider API Key（MiniMax/Alibaba/OpenAI/Anthropic/Google）

---

## 配置清单

### 必需环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `TUSHARE_TOKEN` | Tushare Pro Token | `your_tushare_token` |
| `MINIMAX_API_KEY` | MiniMax API Key（默认 LLM） | `your_minimax_key` |

### 可选环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TRADINGAGENTS_PORT` | Web 服务端口 | `8000` |
| `TRADINGAGENTS_CORS_ORIGINS` | CORS 允许来源（逗号分隔） | `*` |
| `TRADINGAGENTS_API_KEY` | API 认证密钥 | 无（不认证） |
| `DASHSCOPE_API_KEY` | Alibaba Bailian API Key | 无 |
| `ALIYUN_CODING_PLAN_API_KEY` | Alibaba Cloud Coding Plan API Key | 无 |
| `OPENAI_API_KEY` | OpenAI API Key | 无 |

### 配置文件

创建 `.env` 文件：

```bash
# LLM Provider (选择一个)
MINIMAX_API_KEY=your_minimax_api_key
# DASHSCOPE_API_KEY=your_dashscope_key
# ALIYUN_CODING_PLAN_API_KEY=your_coding_plan_key

# Data Source
TUSHARE_TOKEN=your_tushare_token

# Web Configuration
TRADINGAGENTS_PORT=8000
TRADINGAGENTS_CORS_ORIGINS=https://your-domain.com,http://localhost:3000

# Optional: Enable API Key authentication
TRADINGAGENTS_API_KEY=your_secure_api_key
```

---

## Docker 部署

### 1. 构建镜像

```bash
docker-compose build
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 检查健康状态

```bash
curl http://localhost:8000/health
```

### 4. 查看日志

```bash
docker-compose logs -f tradingagents
```

### 5. 停止服务

```bash
docker-compose down
```

---

## 资源建议

### Docker 资源限制

在 `docker-compose.yaml` 中已配置默认限制：

```yaml
deploy:
  resources:
    limits:
      cpus: "2"
      memory: 4G
    reservations:
      cpus: "0.5"
      memory: 1G
```

根据实际负载调整：

| 使用场景 | CPU | 内存 | 说明 |
|----------|-----|------|------|
| 开发/测试 | 1核 | 2GB | 单用户并发 |
| 小规模生产 | 2核 | 4GB | 4 并发任务 |
| 中规模生产 | 4核 | 8GB | 8 并发任务 |

### 并发控制

在 `tradingagents/default_config.py` 中：

```python
"max_concurrent_tasks": 4,  # 最大并发分析任务数
```

建议根据 LLM Provider 的 Rate Limit 设置：
- MiniMax: 建议 4-8 并发
- Alibaba Bailian: 建议 2-4 并发
- OpenAI: 建议 2 并发（Tier 1）

---

## 监控指标

### Prometheus 集成

访问 `/metrics` 端点获取 Prometheus 格式指标：

```bash
curl http://localhost:8000/metrics
```

### 关键指标

| 指标 | 说明 |
|------|------|
| `tradingagents_tasks_total` | 累计任务数 |
| `tradingagents_tasks_by_status{status="completed"}` | 成功任务数 |
| `tradingagents_tasks_by_status{status="failed"}` | 失败任务数 |
| `tradingagents_tasks_active` | 当前活跃任务数 |
| `tradingagents_tokens_input_total` | 累计输入 Token |
| `tradingagents_tokens_output_total` | 累计输出 Token |
| `tradingagents_semaphore_available` | 可用并发槽位 |

### Grafana Dashboard

建议监控：
- 任务成功率（`completed / total`）
- 平均任务耗时（从 `created_at` 到 `completed_at`）
- Token 消耗趋势
- 活跃任务数峰值
- 健康检查状态

---

## 常见问题

### Q: 服务启动后健康检查失败

检查步骤：
1. 查看日志：`docker-compose logs tradingagents`
2. 检查数据库连接：确保 `/app/data/tasks.db` 可写入
3. 检查 API Key：确认 `.env` 中配置正确

### Q: 分析任务卡住不返回

可能原因：
1. LLM Provider 响应慢：检查 `llm_timeout` 配置（默认 300s）
2. 数据源超时：检查 `tool_timeout` 配置（默认 90s）
3. 并发槽位被占用：检查 `/metrics` 的 `tradingagents_semaphore_available`

### Q: 数据获取失败

检查顺序：
1. Tushare Token 是否有效
2. Tushare 账号是否有对应接口权限
3. 网络是否能访问 Tushare API
4. Akshare fallback 是否可用

### Q: 内存占用过高

排查：
1. 检查任务数量：清理旧任务记录
2. 检查日志文件大小：日志会自动轮转（50MB/文件，10 个备份）
3. 检查缓存文件：清理过期缓存

```bash
# 清理过期缓存
curl -X POST http://localhost:8000/api/cache/clear-expired
```

### Q: Token 消耗过多

优化建议：
1. 减少辩论轮数：`max_debate_rounds: 1`
2. 使用更便宜的 LLM：将 `quick_think_llm` 改为 `MiniMax-M2.5`
3. 启用缓存：行业分类和关键词缓存 30 天有效

---

## 安全建议

### 生产环境必须项

1. **设置 CORS 来源**
   ```bash
   TRADINGAGENTS_CORS_ORIGINS=https://your-domain.com
   ```

2. **启用 API Key 认证**
   ```bash
   TRADINGAGENTS_API_KEY=your_secure_random_key
   ```

3. **使用 HTTPS**
   - 配置反向代理（Nginx/Caddy）
   - 或在 Docker 中添加 SSL 证书

4. **定期备份数据库**
   ```bash
   cp /app/data/tasks.db /backup/tasks_$(date +%Y%m%d).db
   ```

### API Key 使用方式

请求时携带：
```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/analyze/start
```

或在 URL 中：
```bash
curl "http://localhost:8000/api/analyze/start?api_key=your_api_key"
```

---

## 版本升级

### 升级步骤

```bash
# 1. 拉取新版本
git pull origin main

# 2. 备份数据
docker-compose exec tradingagents cp /app/data/tasks.db /app/data/tasks.db.bak

# 3. 重新构建
docker-compose build

# 4. 重启服务
docker-compose down && docker-compose up -d

# 5. 验证健康
curl http://localhost:8000/health
```

### 数据迁移

如果数据库结构有变化，系统启动时会自动执行迁移（ALTER TABLE）。

---

## 联系与支持

- GitHub Issues: https://github.com/your-repo/TradingAgents/issues
- 文档: `/docs` 端点查看 API 文档
