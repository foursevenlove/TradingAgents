# TradingAgents A股版 - 快速开始指南

本指南将帮助你在5分钟内开始使用TradingAgents分析A股股票。

## 📋 前置要求

- Python 3.13 或更高版本
- MiniMax API密钥（[免费申请](https://platform.minimaxi.com/)）

## 🚀 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/TradingAgents.git
cd TradingAgents
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置API密钥

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，添加你的MiniMax API密钥：

```bash
MINIMAX_API_KEY=your_api_key_here
```

## 🎯 第一次分析

### 运行程序

```bash
python -m cli.main
```

### 输入信息

程序会提示你输入以下信息：

1. **股票代码**：输入A股代码，例如：
   - `000001.SZ` - 平安银行（深圳主板）
   - `600000.SH` - 浦发银行（上海主板）
   - `688001.SH` - 华兴源创（科创板）
   - `300001.SZ` - 特锐德（创业板）

2. **分析日期**：输入日期，格式：`YYYY-MM-DD`
   - 例如：`2024-03-20`
   - 或直接回车使用今天的日期

3. **选择分析师**：选择你需要的分析师（用逗号分隔）
   - `market` - 市场技术分析师
   - `fundamentals` - 基本面分析师
   - `news` - 新闻分析师
   - `social` - 社交媒体分析师
   - 例如：`market,fundamentals,news`

### 示例会话

```
Welcome to TradingAgents!

Enter stock symbol (e.g., 000001.SZ): 000001.SZ
Enter analysis date (YYYY-MM-DD) [2024-03-20]:
Select analysts (comma-separated):
  - market: Market Technical Analyst
  - fundamentals: Fundamentals Analyst
  - news: News Analyst
  - social: Social Media Analyst
Your selection: market,fundamentals,news

Starting analysis for 000001.SZ...
```

## 📊 理解分析结果

分析完成后，你会看到以下报告：

### 1. 市场技术分析报告
- 技术指标分析（MACD、RSI、布林带等）
- 趋势判断
- 支撑/阻力位
- 成交量分析

### 2. 基本面分析报告
- 财务指标（ROE、市盈率、市净率等）
- 盈利能力分析
- 成长性评估
- A股特色风险（股权质押、商誉减值等）

### 3. 新闻分析报告
- 最新公司公告
- 行业政策影响
- 宏观经济因素
- 重大事件分析

### 4. 投资建议
- 看涨/看跌辩论
- 综合投资计划
- 风险评估
- 最终交易建议：**买入/持有/卖出**

## 🎓 进阶使用

### 分析多只股票

你可以连续运行程序分析多只股票，对比选择：

```bash
# 分析银行板块
python -m cli.main  # 000001.SZ 平安银行
python -m cli.main  # 600000.SH 浦发银行
python -m cli.main  # 600036.SH 招商银行
```

### 自定义配置

编辑 `tradingagents/default_config.py` 来自定义配置：

```python
DEFAULT_CONFIG = {
    # 切换LLM模型
    "deep_think_llm": "MiniMax-M2.7",      # 深度推理
    "quick_think_llm": "MiniMax-M2.5",     # 快速推理

    # 切换数据源
    "data_vendors": {
        "core_stock_apis": "akshare",      # 或 "yfinance"
    },
}
```

### 使用其他LLM提供商

如果你想使用OpenAI或Anthropic：

1. 在 `.env` 中添加相应的API密钥
2. 修改配置：

```python
DEFAULT_CONFIG = {
    "llm_provider": "openai",  # 或 "anthropic"
    "deep_think_llm": "gpt-5.2",
    "quick_think_llm": "gpt-5-mini",
}
```

## 🔍 常见问题

### Q: 如何获取MiniMax API密钥？

A: 访问 [MiniMax平台](https://platform.minimaxi.com/)，注册账号后在控制台创建API密钥。

### Q: 支持哪些股票代码格式？

A: 支持以下格式：
- 带后缀：`000001.SZ`, `600000.SH`
- 不带后缀：`000001`, `600000`（会自动识别市场）

### Q: 数据从哪里来？

A: 默认使用akshare获取A股数据，包括：
- 股票行情数据
- 财务报表
- 公司公告
- 新闻资讯
- A股特色数据（北向资金、融资融券等）

### Q: 分析需要多长时间？

A: 取决于选择的分析师数量和LLM响应速度：
- 单个分析师：约1-2分钟
- 全部分析师：约5-10分钟

### Q: 如何理解最终建议？

A: 最终建议基于多个Agent的综合分析：
- **买入**：看涨因素占优，风险可控
- **持有**：观望为主，等待更好时机
- **卖出**：看跌因素占优，建议止损

### Q: 分析结果准确吗？

A: ⚠️ **重要提示**：
- 分析结果仅供参考，不构成投资建议
- 请结合自己的判断和风险承受能力
- 投资有风险，入市需谨慎

## 📚 下一步

- 阅读 [README_CN.md](README_CN.md) 了解完整功能
- 查看 [Agent详细说明](README_CN.md#-agent详细说明)
- 了解 [A股特色功能](README_CN.md#-a股特色功能)
- 参与 [贡献代码](README_CN.md#-贡献指南)

## 💬 获取帮助

如果遇到问题：

1. 查看 [常见问题](#-常见问题)
2. 搜索 [Issues](https://github.com/yourusername/TradingAgents/issues)
3. 提交新的 [Issue](https://github.com/yourusername/TradingAgents/issues/new)
4. 加入 [讨论区](https://github.com/yourusername/TradingAgents/discussions)

---

**祝你投资顺利！📈**
