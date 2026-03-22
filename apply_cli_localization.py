#!/usr/bin/env python3
"""
CLI完整中文化脚本
系统性地修改main.py中的所有英文文本
"""
import re

# 读取main.py文件
with open('/Users/foursevenlove/DevSpace/code/TradingAgents/cli/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 定义所有需要替换的文本（精确匹配，避免误替换）
replacements = [
    # 表格列标题
    ('progress_table.add_column("Team"', 'progress_table.add_column("团队"'),
    ('progress_table.add_column("Agent"', 'progress_table.add_column("Agent"'),
    ('progress_table.add_column("Status"', 'progress_table.add_column("状态"'),

    # 团队名称（在字典中）
    ('"Analyst Team":', '"分析师团队":'),
    ('"Research Team":', '"研究团队":'),
    ('"Trading Team":', '"交易团队":'),
    ('"Risk Management":', '"风险管理":'),
    ('"Portfolio Management":', '"投资组合管理":'),

    # 状态文本
    ('"pending"', '"待处理"'),
    ('"in_progress"', '"进行中"'),
    ('"completed"', '"已完成"'),
    ('"error"', '"错误"'),

    # Panel标题
    ('title="Progress"', 'title="进度"'),
    ('title="Messages & Tools"', 'title="消息 & 工具"'),
    ('title="Current Report"', 'title="当前报告"'),

    # 报告部分标题
    ('"## Analyst Team Reports"', '"## 分析师团队报告"'),
    ('"## Research Team Decision"', '"## 研究团队决策"'),
    ('"## Trading Team Plan"', '"## 交易团队计划"'),
    ('"### Market Analysis\\n"', '"### 市场分析\\n"'),
    ('"### Social Sentiment\\n"', '"### 社交情绪\\n"'),
    ('"### News Analysis\\n"', '"### 新闻分析\\n"'),
    ('"### Fundamentals Analysis\\n"', '"### 基本面分析\\n"'),

    # section_titles字典
    ('"market_report": "Market Analysis"', '"market_report": "市场分析"'),
    ('"sentiment_report": "Social Sentiment"', '"sentiment_report": "社交情绪"'),
    ('"news_report": "News Analysis"', '"news_report": "新闻分析"'),
    ('"fundamentals_report": "Fundamentals Analysis"', '"fundamentals_report": "基本面分析"'),
    ('"investment_plan": "Research Team Decision"', '"investment_plan": "研究团队决策"'),
    ('"trader_investment_plan": "Trading Team Plan"', '"trader_investment_plan": "交易团队计划"'),
    ('"final_trade_decision": "Portfolio Management Decision"', '"final_trade_decision": "投资组合管理决策"'),
]

# 应用所有替换
for old, new in replacements:
    content = content.replace(old, new)

# 写回文件
with open('/Users/foursevenlove/DevSpace/code/TradingAgents/cli/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("=" * 80)
print("CLI中文化完成！")
print("=" * 80)
print()
print("已完成的修改：")
for i, (old, new) in enumerate(replacements, 1):
    print(f"{i}. {old[:50]}... -> {new[:50]}...")
print()
print("现在运行 'python -m cli.main' 查看完整的中文界面")
