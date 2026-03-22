# OpenClaw 集成快速指南

## 🎯 三种使用方式

### 方式 1：命令行工具（最简单）

直接运行 Python 脚本：

```bash
# 分析股票
python openclaw_integration/stock_analyzer.py 000001.SZ

# 指定日期
python openclaw_integration/stock_analyzer.py 002202.SZ --date 2026-03-22
```

**OpenClaw 中使用：**

```
帮我运行：python /Users/foursevenlove/DevSpace/code/TradingAgents/openclaw_integration/stock_analyzer.py 000001.SZ
```

### 方式 2：API 服务（推荐用于远程调用）

1. 启动 API 服务：

```bash
cd /Users/foursevenlove/DevSpace/code/TradingAgents
./openclaw_integration/start_server.sh
```

2. 在 OpenClaw 中调用：

```
帮我调用 http://localhost:5000/analyze 接口，分析股票 000001.SZ
```

或者使用 curl：

```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "000001.SZ", "date": "2026-03-22"}'
```

### 方式 3：OpenClaw Skill（最集成）

将整个目录作为 Skill 添加到 OpenClaw：

```bash
# 在 OpenClaw 中
/skill add /Users/foursevenlove/DevSpace/code/TradingAgents/openclaw_integration
```

然后直接使用：

```
/stock-analysis 000001.SZ
```

## 📱 Telegram Bot 配置

### 1. 创建 Bot

1. 在 Telegram 找 @BotFather
2. 发送 `/newbot`
3. 按提示设置名称
4. 获取 Token

### 2. 获取 Chat ID

1. 给你的 Bot 发消息
2. 访问：`https://api.telegram.org/bot<TOKEN>/getUpdates`
3. 找到 `chat.id`

### 3. 设置环境变量

```bash
export TELEGRAM_BOT_TOKEN="你的token"
export TELEGRAM_CHAT_ID="你的chat_id"
```

或者创建 `.env` 文件：

```bash
cp openclaw_integration/.env.example .env
# 编辑 .env 文件填入你的配置
```

## 🚀 快速测试

```bash
# 1. 测试 API 服务
python openclaw_integration/test_api.py

# 2. 测试命令行工具
python openclaw_integration/stock_analyzer.py 000001.SZ

# 3. 测试 Telegram 发送
# 确保已配置环境变量，然后运行上面的命令
```

## 💡 OpenClaw 使用示例

### 示例 1：简单分析

```
用户: 帮我分析一下平安银行（000001.SZ）
OpenClaw: 正在运行股票分析...
[自动执行分析]
OpenClaw: 分析完成！报告已发送到您的 Telegram
```

### 示例 2：批量分析

```
用户: 帮我分析这几只股票：000001.SZ, 600000.SH, 002202.SZ
OpenClaw: 正在依次分析...
[自动执行多次分析]
OpenClaw: 全部完成！3份报告已发送到 Telegram
```

### 示例 3：定时任务

```
用户: 每天早上 9:30 自动分析 000001.SZ 并发送到 Telegram
OpenClaw: 已设置定时任务
[每天自动执行]
```

## 🔧 故障排查

### 问题 1：API 服务启动失败

```bash
# 检查端口占用
lsof -i :5000

# 更换端口
export PORT=8000
python openclaw_integration/api_server.py
```

### 问题 2：Telegram 发送失败

```bash
# 测试 Token 是否有效
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# 测试发送消息
curl -X POST https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage \
  -d "chat_id=<YOUR_CHAT_ID>&text=测试消息"
```

### 问题 3：分析失败

```bash
# 查看详细日志
python -m cli.main

# 检查环境变量
echo $MINIMAX_API_KEY
```

## 📚 更多信息

详细文档请查看：`openclaw_integration/README.md`
