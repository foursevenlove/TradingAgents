# TradingAgents - 中国A股版

> 基于多Agent LLM的中国A股金融交易分析框架

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📖 简介

TradingAgents 是一个专门针对中国A股市场改造的多Agent LLM金融交易分析框架。该项目使用LangGraph构建，集成了MiniMax国产大模型和akshare数据源，为A股投资者提供全面的市场分析和交易决策支持。

### 核心特性

- 🤖 **多Agent协作**：12个专业Agent协同工作，提供全方位分析
- 🇨🇳 **A股专用**：针对中国A股市场深度定制，支持T+1、涨跌停等规则
- 🧠 **国产大模型**：默认使用MiniMax-M2.7（推理）和MiniMax-M2.5（快速）
- 📊 **本地数据源**：集成akshare，获取A股实时数据
- 🎯 **强制真实数据**：所有Agent必须调用工具获取真实数据，禁止编造
- 📈 **A股特色指标**：北向资金、融资融券、龙虎榜、大宗交易等

## 🏗️ 系统架构

### Agent团队结构

```
TradingAgents (A股版)
├── 分析师团队 (Analysts)
│   ├── 市场技术分析师 (Market Analyst)
│   ├── 基本面分析师 (Fundamentals Analyst)
│   ├── 新闻分析师 (News Analyst)
│   └── 社交媒体分析师 (Social Media Analyst)
├── 研究团队 (Researchers)
│   ├── 看涨研究员 (Bull Researcher)
│   ├── 看跌研究员 (Bear Researcher)
│   └── 研究经理 (Research Manager)
├── 交易团队 (Trading)
│   └── 交易员 (Trader)
└── 风险管理团队 (Risk Management)
    ├── 激进风险分析师 (Aggressive Analyst)
    ├── 保守风险分析师 (Conservative Analyst)
    ├── 中立风险分析师 (Neutral Analyst)
    └── 风险经理 (Risk Manager)
```

### 工作流程

1. **数据收集阶段**：分析师团队调用工具获取真实数据
2. **研究辩论阶段**：看涨/看跌研究员基于数据进行辩论
3. **投资决策阶段**：研究经理综合评估，制定投资计划
4. **交易执行阶段**：交易员根据计划提出交易建议
5. **风险评估阶段**：风险管理团队评估风险，给出最终决策

## 🚀 快速开始

### 环境要求

- Python 3.13+
- MiniMax API密钥（[申请地址](https://platform.minimaxi.com/)）

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/yourusername/TradingAgents.git
cd TradingAgents
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置环境变量**

创建 `.env` 文件并添加API密钥：

```bash
# MiniMax API密钥（必需）
MINIMAX_API_KEY=your_minimax_api_key_here

# 其他LLM提供商（可选，用于降级）
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

4. **运行分析**

```bash
python -m cli.main
```

### 使用示例

#### 分析A股股票

```bash
# 分析平安银行（000001.SZ）
python -m cli.main

# 按照提示输入：
# 1. 股票代码：000001.SZ
# 2. 分析日期：2024-03-20
# 3. 选择分析师：market, fundamentals, news, social
```

#### 支持的股票代码格式

- **深圳主板**：`000001.SZ`（平安银行）
- **上海主板**：`600000.SH`（浦发银行）
- **科创板**：`688001.SH`（华兴源创）
- **创业板**：`300001.SZ`（特锐德）

## 📊 A股特色功能

### 1. 交易规则适配

- ✅ **T+1交易制度**：当日买入次日才能卖出
- ✅ **涨跌停限制**：
  - 主板：±10%
  - ST股票：±5%
  - 科创板/创业板：±20%
- ✅ **交易时间检查**：9:30-11:30, 13:00-15:00
- ✅ **交易成本计算**：佣金、印花税、过户费

### 2. A股特有数据指标

- 📈 **北向资金流向**：外资通过沪深港通流入A股的资金
- 💰 **融资融券数据**：杠杆资金变化
- 🐉 **龙虎榜数据**：游资和机构动向
- 📦 **大宗交易数据**：大额交易情况
- 🏢 **机构持仓数据**：基金、QFII等持仓
- 📊 **涨跌停统计**：市场情绪指标
- 🎯 **市场情绪指数**：综合情绪评估

### 3. 行业分类本地化

- 🏭 **申万行业分类**：三级行业分类体系
- 🔍 **同行业股票查询**：找到同行业可比公司
- 📈 **行业表现统计**：行业整体表现分析
- ⚖️ **与行业对比**：个股与行业平均对比

## 🔧 配置说明

### 默认配置

项目默认配置位于 `tradingagents/default_config.py`：

```python
DEFAULT_CONFIG = {
    # LLM设置
    "llm_provider": "minimax",
    "deep_think_llm": "MiniMax-M2.7",      # 深度推理模型
    "quick_think_llm": "MiniMax-M2.5",     # 快速推理模型
    "backend_url": "https://api.minimaxi.com/v1",

    # 数据源设置
    "data_vendors": {
        "core_stock_apis": "akshare",       # 股票数据
        "technical_indicators": "akshare",  # 技术指标
        "fundamental_data": "akshare",      # 基本面数据
        "news_data": "akshare",             # 新闻数据
    },
}
```

### 自定义配置

你可以通过环境变量或配置文件覆盖默认配置。

## 📚 Agent详细说明

### 市场技术分析师 (Market Analyst)

**职责**：分析技术指标和市场趋势

**A股特色分析**：
- 重点关注成交量变化（量在价先）
- 考虑T+1制度影响
- 识别重要心理关口（3000点、3500点）
- 关注主力资金动向（大单、北向资金）
- 警惕涨跌停板风险

**使用的技术指标**：
- 趋势类：50日均线、200日均线、10日均线
- 动量类：MACD、RSI
- 波动类：布林带、ATR
- 成交量：VWMA（A股特别重要）

### 基本面分析师 (Fundamentals Analyst)

**职责**：分析公司财务状况和投资价值

**A股特色分析**：
- 股东结构（国资、外资、机构）
- 限售股解禁风险
- 股权质押风险
- 商誉减值风险
- 关联交易分析
- 会计政策评估

**分析维度**：
- 盈利能力：ROE、ROA、净利率
- 成长性：营收增长率、净利润增长率
- 估值水平：市盈率TTM、市净率、PEG
- 财务健康：资产负债率、现金流

### 新闻分析师 (News Analyst)

**职责**：分析新闻和政策影响

**A股特色关注**：
- 政策导向（国务院、央行、证监会）
- 重大会议（两会、中央经济工作会议）
- 公司公告（业绩预告、重组、增减持）
- 行业监管（整顿、政策变化）
- 宏观经济数据（GDP、CPI、PMI）

### 社交媒体分析师 (Social Media Analyst)

**职责**：分析市场情绪和舆论

**A股特色平台**：
- 雪球（专业投资者）
- 东方财富股吧（散户情绪）
- 微博财经话题
- 同花顺、大智慧

**分析重点**：
- KOL观点
- 散户情绪指标
- 市场热点和概念炒作
- 庄家和游资动向

## 🛡️ 强制真实数据机制

所有Agent都配置了强制工具调用机制：

```
🔴 强制要求：你必须调用工具获取真实数据！
🚫 绝对禁止：不允许假设、编造或直接回答任何问题！
```

**工作流程**：
1. Agent必须先调用数据工具
2. 基于真实数据进行分析
3. 如果工具调用失败，必须说明原因
4. 不得编造或假设任何数据

## 🔄 数据源说明

### Akshare数据源

项目使用[akshare](https://github.com/akfamily/akshare)作为主要数据源：

- ✅ 免费开源
- ✅ 数据全面（股票、基金、期货、债券等）
- ✅ 更新及时
- ✅ 支持A股特色数据

### 数据降级机制

如果akshare数据获取失败，系统会自动降级到yfinance：

```
akshare (主) → yfinance (备) → alpha_vantage (备)
```

## 📈 使用场景

### 1. 日常选股分析

```bash
# 分析多只股票，对比选择
python -m cli.main
# 输入：000001.SZ, 600000.SH, 600036.SH
```

### 2. 持仓股票跟踪

```bash
# 定期分析持仓股票
python -m cli.main
# 输入持仓股票代码
```

### 3. 行业研究

```bash
# 分析同行业多只股票
# 使用行业分类功能找到同行业股票
```

### 4. 风险评估

```bash
# 重点使用风险管理团队
# 评估持仓风险和市场风险
```

## ⚠️ 免责声明

**重要提示**：

1. 本项目仅供学习和研究使用
2. 所有分析结果仅供参考，不构成投资建议
3. 投资有风险，入市需谨慎
4. 请根据自身风险承受能力做出投资决策
5. 作者不对使用本项目造成的任何损失负责

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

### 贡献方式

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 开发指南

- 遵循PEP 8代码规范
- 添加适当的注释和文档
- 编写单元测试
- 更新相关文档

## 📝 更新日志

### v0.3.0 (2024-03-22) - A股专版

**新增功能**：
- ✅ 接入MiniMax国产大模型
- ✅ 接入akshare A股数据源
- ✅ 所有Agent prompt中文化和A股深度定制
- ✅ A股交易规则适配（T+1、涨跌停等）
- ✅ A股特有数据指标（北向资金、融资融券等）
- ✅ 申万行业分类本地化
- ✅ 强制真实数据机制

**改进**：
- 🔧 优化Agent协作流程
- 🔧 增强错误处理和数据验证
- 🔧 改进报告格式和可读性

### v0.2.1 (之前版本)

- 支持多个LLM提供商
- 支持多个数据源
- 基础的多Agent协作

## 📞 联系方式

- **项目主页**：[GitHub](https://github.com/yourusername/TradingAgents)
- **问题反馈**：[Issues](https://github.com/yourusername/TradingAgents/issues)
- **讨论交流**：[Discussions](https://github.com/yourusername/TradingAgents/discussions)

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM应用框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent工作流框架
- [Akshare](https://github.com/akfamily/akshare) - A股数据源
- [MiniMax](https://www.minimaxi.com/) - 国产大模型
- [yfinance](https://github.com/ranaroussi/yfinance) - 备用数据源

---

**⭐ 如果这个项目对你有帮助，请给个Star支持一下！**
