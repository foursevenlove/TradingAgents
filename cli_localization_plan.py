#!/usr/bin/env python3
"""
CLI中文化和MiniMax集成脚本
一次性完成所有必要的修改
"""

# 需要修改的内容
modifications = {
    "cli/utils.py": {
        "分析师选择": {
            "old": 'ANALYST_ORDER = [\n    ("Market Analyst", AnalystType.MARKET),\n    ("Social Media Analyst", AnalystType.SOCIAL),\n    ("News Analyst", AnalystType.NEWS),\n    ("Fundamentals Analyst", AnalystType.FUNDAMENTALS),\n]',
            "new": 'ANALYST_ORDER = [\n    ("市场技术分析师 (Market Analyst)", AnalystType.MARKET),\n    ("社交媒体分析师 (Social Media Analyst)", AnalystType.SOCIAL),\n    ("新闻分析师 (News Analyst)", AnalystType.NEWS),\n    ("基本面分析师 (Fundamentals Analyst)", AnalystType.FUNDAMENTALS),\n]'
        },
        "选择分析师提示": {
            "old": '"Select Your [Analysts Team]:"',
            "new": '"选择分析师团队 [Analysts Team]:"'
        },
        "选择分析师说明": {
            "old": '"\n- Press Space to select/unselect analysts\n- Press \'a\' to select/unselect all\n- Press Enter when done"',
            "new": '"\n- 按空格键选择/取消选择分析师\n- 按 \'a\' 全选/取消全选\n- 按回车键完成选择"'
        },
        "未选择分析师": {
            "old": '"You must select at least one analyst."',
            "new": '"必须至少选择一个分析师"'
        },
        "研究深度选项": {
            "old": 'DEPTH_OPTIONS = [\n        ("Shallow - Quick research, few debate and strategy discussion rounds", 1),\n        ("Medium - Middle ground, moderate debate rounds and strategy discussion", 3),\n        ("Deep - Comprehensive research, in depth debate and strategy discussion", 5),\n    ]',
            "new": 'DEPTH_OPTIONS = [\n        ("浅层 - 快速研究，较少辩论和策略讨论轮次", 1),\n        ("中等 - 中等深度，适度的辩论轮次和策略讨论", 3),\n        ("深度 - 全面研究，深入的辩论和策略讨论", 5),\n    ]'
        },
        "选择研究深度": {
            "old": '"Select Your [Research Depth]:"',
            "new": '"选择研究深度 [Research Depth]:"'
        },
        "添加MiniMax到快速模型": {
            "old": '    SHALLOW_AGENT_OPTIONS = {\n        "openai": [',
            "new": '    SHALLOW_AGENT_OPTIONS = {\n        "minimax": [\n            ("MiniMax-M2.5 - 快速推理，适合简单任务", "MiniMax-M2.5"),\n            ("MiniMax-M2.1 - 轻量级模型", "MiniMax-M2.1"),\n        ],\n        "openai": ['
        },
        "添加MiniMax到深度模型": {
            "old": '    DEEP_AGENT_OPTIONS = {\n        "openai": [',
            "new": '    DEEP_AGENT_OPTIONS = {\n        "minimax": [\n            ("MiniMax-M2.7 - 深度推理，最强能力", "MiniMax-M2.7"),\n            ("MiniMax-M2.5 - 平衡速度和能力", "MiniMax-M2.5"),\n        ],\n        "openai": ['
        },
        "选择快速模型": {
            "old": '"Select Your [Quick-Thinking LLM Engine]:"',
            "new": '"选择快速推理模型 [Quick-Thinking LLM]:"'
        },
        "选择深度模型": {
            "old": '"Select Your [Deep-Thinking LLM Engine]:"',
            "new": '"选择深度推理模型 [Deep-Thinking LLM]:"'
        },
        "添加MiniMax到提供商列表": {
            "old": '    BASE_URLS = [\n        ("OpenAI", "https://api.openai.com/v1"),',
            "new": '    BASE_URLS = [\n        ("MiniMax", "https://api.minimaxi.com/v1"),\n        ("OpenAI", "https://api.openai.com/v1"),'
        },
        "选择LLM提供商": {
            "old": '"Select your LLM Provider:"',
            "new": '"选择LLM提供商 [LLM Provider]:"'
        }
    }
}

print("=" * 80)
print("CLI中文化和MiniMax集成修改清单")
print("=" * 80)
print()
print("需要修改的内容：")
print()
for file, changes in modifications.items():
    print(f"文件: {file}")
    for change_name in changes.keys():
        print(f"  - {change_name}")
    print()

print("=" * 80)
print("请使用Edit工具逐一应用这些修改")
print("=" * 80)
