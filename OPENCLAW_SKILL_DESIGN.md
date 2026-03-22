# TradingAgents OpenClaw Skill 实现方案

## 需求分析

### 用户工作流程
1. 用户在Telegram Bot上给OpenClaw发消息："帮我分析一下000001.SZ这只股票"
2. OpenClaw识别意图，触发`stock-analysis` skill
3. Skill在后台运行股票分析（耗时较长，可能5-10分钟）
4. 分析完成后，自动将结果推送到用户的Telegram Bot

### 技术挑战
- **长时间运行**：股票分析需要5-10分钟，不能阻塞OpenClaw
- **异步通知**：分析完成后需要主动推送结果到Telegram
- **参数传递**：需要从OpenClaw传递股票代码和日期参数

## 实现方案

### 方案架构

```
用户 (Telegram)
    ↓
OpenClaw (识别意图)
    ↓
stock-analysis skill (触发)
    ↓
analyze_stock.sh (后台执行)
    ↓
python -m cli.main (运行分析)
    ↓
生成报告
    ↓
Telegram Bot API (推送结果)
    ↓
用户 (Telegram) 收到报告
```

### Skill目录结构

```
~/.openclaw/workspace/skills/stock-analysis/
├── SKILL.md              # Skill定义和说明
├── analyze_stock.sh      # 主执行脚本
├── send_telegram.py      # Telegram推送脚本
└── README.md             # 使用说明
```

### 核心文件设计

#### 1. SKILL.md
```markdown
---
name: stock-analysis
description: "分析中国A股股票，生成详细的投资分析报告。支持基本面分析、技术分析、新闻分析等多维度评估。"
version: "1.0.0"
author: "TradingAgents"
license: "MIT"
tags: ["finance", "stock", "analysis", "a-share"]
---

# 股票分析 Skill

## 功能说明
这个skill可以分析中国A股市场的股票，生成包含以下内容的详细报告：
- 基本面分析（财务数据、估值指标）
- 技术分析（K线、技术指标）
- 新闻分析（公司公告、行业新闻）
- 社交媒体情绪分析
- 投资建议和风险评估

## 使用场景
当用户说以下内容时，应该触发这个skill：
- "帮我分析一下[股票代码]"
- "看看[股票代码]怎么样"
- "给我一份[股票代码]的分析报告"
- "研究一下[股票代码]"
- "[股票代码]值得投资吗"

## 参数
- `ticker` (必需): 股票代码，格式如 000001.SZ, 600000.SH
- `date` (可选): 分析日期，格式 YYYY-MM-DD，默认为今天

## 执行方式
```bash
bash analyze_stock.sh <ticker> [date]
```

## 注意事项
- 分析过程需要5-10分钟，会在后台运行
- 完成后会自动发送报告到Telegram
- 需要配置TELEGRAM_BOT_TOKEN和TELEGRAM_CHAT_ID环境变量
```

#### 2. analyze_stock.sh
```bash
#!/bin/bash
# 股票分析主脚本

set -e

# 获取参数
TICKER=$1
DATE=${2:-$(date +%Y-%m-%d)}

# 检查参数
if [ -z "$TICKER" ]; then
    echo "错误：缺少股票代码参数"
    echo "用法: $0 <ticker> [date]"
    exit 1
fi

# 获取TradingAgents项目路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/Users/foursevenlove/DevSpace/code/TradingAgents"

# 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    echo "错误：找不到TradingAgents项目目录: $PROJECT_DIR"
    exit 1
fi

# 日志文件
LOG_FILE="$SCRIPT_DIR/analysis_${TICKER}_$(date +%Y%m%d_%H%M%S).log"

echo "开始分析股票: $TICKER (日期: $DATE)"
echo "日志文件: $LOG_FILE"

# 在后台运行分析
(
    cd "$PROJECT_DIR"

    # 运行股票分析
    echo "正在运行股票分析..." | tee -a "$LOG_FILE"
    echo -e "${TICKER}\n${DATE}\n" | python -m cli.main >> "$LOG_FILE" 2>&1

    # 检查是否成功
    if [ $? -eq 0 ]; then
        echo "分析完成！" | tee -a "$LOG_FILE"

        # 查找生成的报告文件
        REPORT_DIR="$PROJECT_DIR/results"
        LATEST_REPORT=$(ls -t "$REPORT_DIR"/*_final_report.md 2>/dev/null | head -1)

        if [ -n "$LATEST_REPORT" ]; then
            echo "找到报告文件: $LATEST_REPORT" | tee -a "$LOG_FILE"

            # 发送到Telegram
            python "$SCRIPT_DIR/send_telegram.py" \
                --ticker "$TICKER" \
                --date "$DATE" \
                --report "$LATEST_REPORT" \
                --log "$LOG_FILE"
        else
            echo "警告：未找到报告文件" | tee -a "$LOG_FILE"
        fi
    else
        echo "分析失败，请查看日志: $LOG_FILE" | tee -a "$LOG_FILE"

        # 发送错误通知到Telegram
        python "$SCRIPT_DIR/send_telegram.py" \
            --ticker "$TICKER" \
            --error "分析失败" \
            --log "$LOG_FILE"
    fi
) &

# 获取后台进程PID
BG_PID=$!
echo "分析任务已在后台启动 (PID: $BG_PID)"
echo "预计需要5-10分钟，完成后会自动发送到Telegram"
```

#### 3. send_telegram.py
```python
#!/usr/bin/env python3
"""
发送股票分析报告到Telegram Bot
"""
import os
import sys
import argparse
import requests
from pathlib import Path

def send_telegram_message(text: str, chat_id: str = None, bot_token: str = None):
    """发送文本消息到Telegram"""
    bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        print("错误：未配置TELEGRAM_BOT_TOKEN或TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"发送消息失败: {e}")
        return False

def send_telegram_file(file_path: str, caption: str = None, chat_id: str = None, bot_token: str = None):
    """发送文件到Telegram"""
    bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        print("错误：未配置TELEGRAM_BOT_TOKEN或TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id}
            if caption:
                data['caption'] = caption

            response = requests.post(url, data=data, files=files, timeout=30)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"发送文件失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='发送股票分析报告到Telegram')
    parser.add_argument('--ticker', required=True, help='股票代码')
    parser.add_argument('--date', help='分析日期')
    parser.add_argument('--report', help='报告文件路径')
    parser.add_argument('--log', help='日志文件路径')
    parser.add_argument('--error', help='错误信息')

    args = parser.parse_args()

    if args.error:
        # 发送错误通知
        message = f"❌ 股票分析失败\n\n"
        message += f"股票代码: {args.ticker}\n"
        message += f"错误: {args.error}\n"
        if args.log and os.path.exists(args.log):
            with open(args.log, 'r') as f:
                log_content = f.read()[-1000:]  # 只取最后1000字符
                message += f"\n日志摘要:\n```\n{log_content}\n```"

        send_telegram_message(message)
    else:
        # 发送成功通知
        message = f"✅ 股票分析完成\n\n"
        message += f"股票代码: {args.ticker}\n"
        if args.date:
            message += f"分析日期: {args.date}\n"
        message += f"\n报告已生成，请查看附件。"

        send_telegram_message(message)

        # 发送报告文件
        if args.report and os.path.exists(args.report):
            caption = f"{args.ticker} 完整分析报告"
            send_telegram_file(args.report, caption)

if __name__ == '__main__':
    main()
```

## 部署步骤

### 1. 创建Skill目录
```bash
mkdir -p ~/.openclaw/workspace/skills/stock-analysis
cd ~/.openclaw/workspace/skills/stock-analysis
```

### 2. 复制文件
将上述三个文件（SKILL.md, analyze_stock.sh, send_telegram.py）复制到skill目录

### 3. 设置权限
```bash
chmod +x analyze_stock.sh
chmod +x send_telegram.py
```

### 4. 配置环境变量
在OpenClaw的配置中添加：
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

或者在`~/.openclaw/openclaw.json`中配置

### 5. 测试Skill
```bash
# 手动测试
bash analyze_stock.sh 000001.SZ 2026-03-22

# 通过OpenClaw测试
# 在Telegram Bot中发送："帮我分析一下000001.SZ"
```

## 工作流程说明

1. **用户发起请求**
   - 用户在Telegram中对OpenClaw说："帮我分析一下000001.SZ"

2. **OpenClaw识别意图**
   - OpenClaw的Brain解析用户意图
   - 匹配到`stock-analysis` skill
   - 提取参数：ticker=000001.SZ

3. **触发Skill执行**
   - OpenClaw调用`analyze_stock.sh 000001.SZ`
   - 脚本在后台启动分析任务
   - 立即返回确认消息给用户

4. **后台分析**
   - 脚本切换到TradingAgents项目目录
   - 运行`python -m cli.main`
   - 输入股票代码和日期
   - 等待分析完成（5-10分钟）

5. **推送结果**
   - 分析完成后，查找生成的报告文件
   - 调用`send_telegram.py`
   - 通过Telegram Bot API发送消息和文件
   - 用户在Telegram中收到完整报告

## 优势

1. **非阻塞**：分析在后台运行，不阻塞OpenClaw
2. **自动推送**：完成后自动发送到Telegram，无需轮询
3. **错误处理**：失败时也会发送通知
4. **日志记录**：每次分析都有详细日志
5. **灵活性**：可以通过OpenClaw或命令行直接调用

## 注意事项

1. **路径配置**：需要修改`analyze_stock.sh`中的`PROJECT_DIR`为实际路径
2. **环境变量**：必须配置Telegram Bot Token和Chat ID
3. **依赖安装**：确保TradingAgents项目的依赖已安装
4. **权限设置**：脚本需要可执行权限
5. **网络访问**：需要能访问Telegram API

## 扩展功能

未来可以添加：
- 批量分析多只股票
- 定时分析（结合OpenClaw的Cron功能）
- 自定义分析参数（如只做技术分析）
- 分析结果缓存
- 实时价格提醒
