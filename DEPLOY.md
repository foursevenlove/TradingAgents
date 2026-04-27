# TradingAgents 部署指南

## 方式一：Ubuntu 直接部署（推荐）

### 1. 安装依赖

```bash
# Ubuntu 系统依赖
sudo apt update
sudo apt install python3 python3-pip python3-venv nodejs npm

# 克隆项目
git clone https://github.com/your-repo/TradingAgents.git
cd TradingAgents

# 配置环境变量
cp .env.example .env
# 编辑 .env 添加 API Keys
```

### 2. 一键部署

```bash
# 首次部署：安装依赖 + 构建前端 + 启动服务
./start_ubuntu.sh all
```

### 3. 常用命令

```bash
./start_ubuntu.sh install   # 仅安装 Python 依赖
./start_ubuntu.sh build     # 仅构建前端
./start_ubuntu.sh start     # 启动服务
./start_ubuntu.sh stop      # 停止服务
./start_ubuntu.sh restart   # 重启服务
./start_ubuntu.sh help      # 显示帮助
```

### 4. 后台运行（生产环境）

```bash
# 使用 nohup 后台运行
nohup ./start_ubuntu.sh start > logs/server.log 2>&1 &

# 或使用 systemd（推荐）
```

创建 systemd 服务文件 `/etc/systemd/system/tradingagents.service`：

```ini
[Unit]
Description=TradingAgents Web Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/TradingAgents
Environment="TRADINGAGENTS_WEB_PORT=8000"
ExecStart=/path/to/TradingAgents/venv/bin/uvicorn web.backend.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable tradingagents
sudo systemctl start tradingagents
sudo systemctl status tradingagents
```

---

## 方式二：Docker 部署

### 1. 准备环境变量

在服务器上创建 `.env` 文件（或直接使用环境变量）：

```bash
# 必需 - 选择一个 LLM Provider
MINIMAX_API_KEY=your_minimax_key
# 或者使用阿里巴巴通义千问
DASHSCOPE_API_KEY=your_dashscope_key

# 必需 - Tushare Pro Token（A股数据）
TUSHARE_TOKEN=your_tushare_token

# 可选 - 自定义端口
TRADINGAGENTS_PORT=8000
```

### 2. 构建并启动

```bash
# 构建镜像并启动
docker compose up -d --build

# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f tradingagents
```

### 3. 访问应用

打开浏览器访问: `http://<服务器IP>:8000`

API 文档: `http://<服务器IP>:8000/docs`

## 常用命令

```bash
# 停止服务
docker compose down

# 重启服务
docker compose restart

# 更新部署（重新构建）
docker compose up -d --build

# 清理旧镜像
docker image prune -f
```

## 数据持久化

以下数据通过 Docker Volume 持久化：
- `tradingagents_data`: 任务数据库
- `tradingagents_logs`: 运行日志
- `tradingagents_reports`: 分析报告
- `tradingagents_results`: 分析结果

## 目录结构

```
/app/
├── tradingagents/     # 核心框架代码
├── cli/              # CLI 工具
├── web/
│   ├── backend/      # FastAPI 后端
│   └── frontend/dist/ # Vue 前端静态文件
├── logs/             # 运行日志
├── reports/          # 分析报告
├── results/          # 分析结果
└── data/             # 数据库文件
```

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `TRADINGAGENTS_PORT` | Web 服务端口 | 8000 |
| `MINIMAX_API_KEY` | MiniMax API Key | - |
| `DASHSCOPE_API_KEY` | 阿里巴巴通义千问 API Key | - |
| `TUSHARE_TOKEN` | Tushare Pro Token | - |

## 故障排查

```bash
# 检查容器健康状态
docker compose ps

# 查看详细日志
docker compose logs --tail=100 tradingagents

# 进入容器调试
docker compose exec tradingagents bash
```