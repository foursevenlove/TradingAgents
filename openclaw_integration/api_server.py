#!/usr/bin/env python3
"""
TradingAgents API Server for OpenClaw Integration
提供 HTTP API 接口供 OpenClaw 调用
"""

from flask import Flask, request, jsonify
import sys
import os
from datetime import datetime
import json
import requests
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

# Telegram Bot 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram_message(message: str, chat_id: str = None):
    """发送消息到 Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ 未配置 TELEGRAM_BOT_TOKEN")
        return False

    chat_id = chat_id or TELEGRAM_CHAT_ID
    if not chat_id:
        print("⚠️ 未配置 TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Telegram 消息长度限制
    if len(message) > 4000:
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": chat_id,
                "text": f"📊 第 {i+1}/{len(chunks)} 部分\n\n{chunk}",
                "parse_mode": "Markdown"
            }
            try:
                requests.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"❌ Telegram 发送失败: {e}")
                return False
    else:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ Telegram 发送失败: {e}")
            return False

    return True


def send_telegram_file(file_path: str, caption: str = "", chat_id: str = None):
    """发送文件到 Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return False

    chat_id = chat_id or TELEGRAM_CHAT_ID
    if not chat_id:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"

    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id, 'caption': caption}
            requests.post(url, files=files, data=data, timeout=30)
        return True
    except Exception as e:
        print(f"❌ 文件发送失败: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "service": "TradingAgents API"})


@app.route('/analyze', methods=['POST'])
def analyze_stock():
    """
    分析股票接口

    请求格式:
    {
        "ticker": "000001.SZ",
        "date": "2026-03-22",
        "telegram_chat_id": "可选"
    }
    """
    try:
        data = request.get_json()
        ticker = data.get('ticker')
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        telegram_chat_id = data.get('telegram_chat_id', TELEGRAM_CHAT_ID)

        if not ticker:
            return jsonify({"error": "缺少 ticker 参数"}), 400

        # 运行分析
        print(f"🚀 开始分析 {ticker} ({date})")

        # 调用 CLI 主程序
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'cli.main'],
            input=f"{ticker}\n{date}\n",
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        if result.returncode != 0:
            error_msg = f"分析失败: {result.stderr}"
            return jsonify({"error": error_msg}), 500

        # 查找生成的报告
        results_dir = Path(f"results/{ticker}/{date}/reports")

        if not results_dir.exists():
            return jsonify({"error": "未找到分析报告"}), 500

        # 读取最终决策报告
        final_report = results_dir / "final_trade_decision.md"
        if final_report.exists():
            with open(final_report, 'r', encoding='utf-8') as f:
                report_content = f.read()

            # 发送到 Telegram
            if telegram_chat_id:
                message = f"📊 *{ticker} 股票分析报告*\n"
                message += f"📅 日期: {date}\n\n"
                message += report_content[:3900]  # 限制长度

                send_telegram_message(message, telegram_chat_id)

                # 发送完整报告文件
                send_telegram_file(str(final_report), f"{ticker} 完整分析报告", telegram_chat_id)

        return jsonify({
            "status": "success",
            "ticker": ticker,
            "date": date,
            "reports_dir": str(results_dir),
            "message": "分析完成，报告已生成"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 TradingAgents API Server 启动在端口 {port}")
    print(f"📱 Telegram Bot Token: {'已配置' if TELEGRAM_BOT_TOKEN else '未配置'}")
    print(f"💬 Telegram Chat ID: {'已配置' if TELEGRAM_CHAT_ID else '未配置'}")
    app.run(host='0.0.0.0', port=port, debug=False)
