# TradingAgents OpenClaw 集成

通过 OpenClaw 运行股票分析并发送到 Telegram Bot。

## 功能特性

- 🤖 通过 OpenClaw 自然语言触发股票分析
- 📊 自动生成完整的 A股分析报告
- 📱 自动发送结果到 Telegram Bot
- 🔄 支持随时随地远程调用

## 架构设计

```
用户 → OpenClaw → API Server → TradingAgents → 生成报告 → Telegram Bot
```

## 快速开始

### 1. 安装依赖

```bash
pip install flask requests python-telegram-bot
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# API 服务端口（可选）
PORT=5000
```

### 3. 启动 API 服务

```bash
cd /Users/foursevenlove/DevSpace/code/TradingAgents
python openclaw_integration/api_server.py
```

服务将在 `http://localhost:5000` 启动。

### 4. 测试 API

```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "000001.SZ",
    "date": "2026-03-22"
  }'
```

### 5. OpenClaw 集成

#### 方式 1：直接调用 API（推荐）

在 OpenClaw 中使用自然语言：

```
帮我分析股票 000001.SZ
```

OpenClaw 会自动调用 API 并返回结果。

#### 方式 2：创建 OpenClaw Skill

将 `openclaw_integration` 目录作为 Skill 添加到 OpenClaw：

```bash
# 在 OpenClaw 中
/skill add /Users/foursevenlove/DevSpace/code/TradingAgents/openclaw_integration
```

然后使用：

```
/stock-analysis 000001.SZ
```

## 使用示例

### 通过 OpenClaw 分析股票

```
用户: 帮我分析一下金风科技（002202）的投资价值
OpenClaw: 正在调用股票分析服务...
[系统自动运行分析]
OpenClaw: 分析完成！报告已发送到您的 Telegram
```

### 通过 API 直接调用

```python
import requests

response = requests.post('http://localhost:5000/analyze', json={
    'ticker': '002202.SZ',
    'date': '2026-03-22',
    'telegram_chat_id': 'your_chat_id'  # 可选
})

print(response.json())
```

## Telegram Bot 配置

### 1. 创建 Telegram Bot

1. 在 Telegram 中找到 @BotFather
2. 发送 `/newbot` 创建新 Bot
3. 按提示设置 Bot 名称
4. 获取 Bot Token

### 2. 获取 Chat ID

1. 启动你的 Bot
2. 发送任意消息给 Bot
3. 访问：`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. 在返回的 JSON 中找到 `chat.id`

### 3. 配置环境变量

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
export TELEGRAM_CHAT_ID="123456789"
```

## API 接口文档

### POST /analyze

分析股票并生成报告。

**请求参数：**

```json
{
  "ticker": "000001.SZ",           // 必需：股票代码
  "date": "2026-03-22",            // 可选：分析日期，默认今天
  "telegram_chat_id": "123456789"  // 可选：Telegram Chat ID
}
```

**响应示例：**

```json
{
  "status": "success",
  "ticker": "000001.SZ",
  "date": "2026-03-22",
  "reports_dir": "results/000001.SZ/2026-03-22/reports",
  "message": "分析完成，报告已生成"
}
```

### GET /health

健康检查接口。

**响应示例：**

```json
{
  "status": "ok",
  "service": "TradingAgents API"
}
```

## 部署到云服务器

### 使用 systemd 守护进程

创建 `/etc/systemd/system/tradingagents-api.service`：

```ini
[Unit]
Description=TradingAgents API Server
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/TradingAgents
Environment="TELEGRAM_BOT_TOKEN=your_token"
Environment="TELEGRAM_CHAT_ID=your_chat_id"
ExecStart=/usr/bin/python3 openclaw_integration/api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable tradingagents-api
sudo systemctl start tradingagents-api
```

### 使用 Docker

创建 `Dockerfile`：

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt
RUN pip install flask requests

ENV PORT=5000
EXPOSE 5000

CMD ["python", "openclaw_integration/api_server.py"]
```

构建并运行：

```bash
docker build -t tradingagents-api .
docker run -d -p 5000:5000 \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHAT_ID=your_chat_id \
  tradingagents-api
```

## 高级用法

### 定时分析

使用 OpenClaw 的定时任务功能：

```
每天早上 9:30 分析 000001.SZ 并发送到 Telegram
```

### 批量分析

```python
import requests

stocks = ['000001.SZ', '600000.SH', '002202.SZ']

for stock in stocks:
    response = requests.post('http://localhost:5000/analyze', json={
        'ticker': stock,
        'date': '2026-03-22'
    })
    print(f"{stock}: {response.json()['message']}")
```

## 故障排查

### API 服务无法启动

检查端口是否被占用：

```bash
lsof -i :5000
```

### Telegram 消息发送失败

1. 检查 Bot Token 是否正确
2. 检查 Chat ID 是否正确
3. 确保 Bot 已启动并与你有对话

### 分析失败

查看日志：

```bash
tail -f logs/tradingagents.log
```

## 安全建议

1. **不要将 API 直接暴露到公网**，使用反向代理（Nginx）
2. **添加 API 认证**，使用 API Key 或 JWT
3. **限制请求频率**，防止滥用
4. **使用 HTTPS**，保护数据传输安全

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
