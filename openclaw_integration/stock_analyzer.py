#!/usr/bin/env python3
"""
OpenClaw 股票分析工具
可以直接被 OpenClaw 调用的命令行工具
"""

import sys
import os
import argparse
from datetime import datetime
import subprocess
import requests
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def send_to_telegram(message: str, file_path: str = None):
    """发送消息到 Telegram"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️  未配置 Telegram，跳过发送")
        return False

    # 发送文本消息
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
        print("✅ 消息已发送到 Telegram")
    except Exception as e:
        print(f"❌ Telegram 发送失败: {e}")
        return False

    # 发送文件
    if file_path and os.path.exists(file_path):
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                requests.post(url, files={'document': f}, data={
                    'chat_id': chat_id,
                    'caption': '📊 完整分析报告'
                }, timeout=30)
            print("✅ 报告文件已发送到 Telegram")
        except Exception as e:
            print(f"❌ 文件发送失败: {e}")

    return True


def analyze_stock(ticker: str, date: str = None):
    """分析股票"""
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f"🚀 开始分析 {ticker} ({date})")

    # 运行分析
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [sys.executable, '-m', 'cli.main'],
        input=f"{ticker}\n{date}\n",
        capture_output=True,
        text=True,
        cwd=project_dir
    )

    if result.returncode != 0:
        print(f"❌ 分析失败: {result.stderr}")
        return False

    # 查找报告
    results_dir = Path(project_dir) / "results" / ticker / date / "reports"
    if not results_dir.exists():
        print("❌ 未找到分析报告")
        return False

    # 读取最终决策报告
    final_report = results_dir / "final_trade_decision.md"
    if not final_report.exists():
        print("❌ 未找到最终决策报告")
        return False

    with open(final_report, 'r', encoding='utf-8') as f:
        report_content = f.read()

    print("\n" + "="*60)
    print("📊 分析完成！")
    print("="*60)
    print(f"报告目录: {results_dir}")

    # 发送到 Telegram
    message = f"📊 *{ticker} 股票分析报告*\n"
    message += f"📅 日期: {date}\n\n"
    message += report_content[:3900]  # 限制长度

    send_to_telegram(message, str(final_report))

    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='TradingAgents 股票分析工具 - OpenClaw 集成版'
    )
    parser.add_argument(
        'ticker',
        help='股票代码，例如: 000001.SZ, 600000.SH, 002202.SZ'
    )
    parser.add_argument(
        '--date',
        help='分析日期，格式: YYYY-MM-DD，默认为今天',
        default=None
    )

    args = parser.parse_args()

    # 运行分析
    success = analyze_stock(args.ticker, args.date)

    if success:
        print("\n✅ 分析成功完成！")
        sys.exit(0)
    else:
        print("\n❌ 分析失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
