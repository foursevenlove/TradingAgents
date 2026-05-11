# 股票推荐系统实现文档

## 系统概述

TradingAgents 股票推荐系统在现有个股分析框架基础上，新增了"股票发现/推荐"能力，从"分析你指定的股票"升级为"告诉你该关注哪些股票"。

**核心设计原则：**
- LLM只输出投资主题/关键词，不输出股票代码（避免幻觉）
- 股票选择完全数据驱动（使用真实市场数据）
- 两种模式：每日热点追踪（轻量）+ 每周深度推荐（完整pipeline）

---

## 系统架构

```
用户输入日期
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 1: 信号采集（数据驱动，程序化）                        │
│  ├─ ThemeExtractor: Tushare新闻 → LLM提取投资主题            │
│  ├─ StockScreener: akshare全市场扫描 → 候选股票池             │
│  └─ 输出：主题列表 + 原始候选池（30-50只）                    │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 2: 主题-股票映射（数据驱动，程序化）                   │
│  ├─ IndustryMapper: 主题关键词 → 申万行业分类                 │
│  ├─ 在行业成分股中按资金流向/技术异动排序                      │
│  └─ 输出：每个主题的TOP候选（3-5只/主题）                     │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 3: 深度验证（复用现有TradingAgentsGraph）              │
│  ├─ 每日模式：市场分析师 + 新闻分析师（轻量）                  │
│  ├─ 每周模式：全部4分析师 + 完整辩论（深度）                  │
│  └─ 输出：每只股票的决策信号 + 置信度                         │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 4: 推荐报告生成                                        │
│  └─ 综合主题分析 + 个股深度分析 → 结构化推荐报告              │
└──────────────────────────────────────────────────────────────┘
```

---

## 新增模块清单

### 1. ThemeExtractor (`tradingagents/recommendation/theme_extractor.py`)

**功能：** 从财经新闻数据提取投资主题

**数据源改进（v0.2.0）：**
- 新增 `get_news_for_recommendation()` 接口，通过 `route_to_vendor("get_recommendation_news")` 获取新闻
- Tushare primary：cls快讯(6小时分段) + major_news(12小时分段) + cctv_news(政策)
- Akshare fallback：财联社快讯 + 新闻联播
- 复用三层新闻架构的分段获取逻辑，避免1500条上限

**核心方法：**
- `get_news_for_recommendation(look_back_days, max_articles)` - 获取推荐系统新闻
- `get_news_from_tushare()` - 向后兼容，委托给新接口
- `extract_themes(news_list, max_themes)` - LLM提取主题（含fallback）
- `get_today_themes(look_back_days)` - 获取今日/本周主题

**输出格式：**
```json
{
  "name": "AI算力基础设施",
  "confidence": 0.90,
  "reason": "AI服务器需求增长",
  "keywords": ["算力", "GPU", "数据中心"],
  "related_industries": ["计算机应用", "通信设备"]
}
```

**特性：**
- 每日推荐：look_back_days=1（过去1天新闻）
- 每周推荐：look_back_days=7（过去7天新闻）
- LLM调用失败时自动切换到关键词匹配fallback
- 严禁输出股票代码（核心约束）

---

### 2. StockScreener (`tradingagents/recommendation/stock_screener.py`)

**功能：** 全市场多因子筛选，纯数据驱动

**数据源：** akshare Sina实时行情（eastmoney接口被屏蔽）

**核心方法：**
- `get_top_gainers(top_n)` - 获取涨幅榜TOP N
- `screen(min_change_pct, max_change_pct, min_amount, top_n)` - 多条件筛选
- `add_industry_to_stocks(df)` - 添加行业分类

**评分因子：**
- 涨幅权重：40%
- 成交额权重：40%
- 动量权重：20%

**输出：** DataFrame（code, name, price, change_pct, amount, score, industry）

---

### 3. IndustryMapper (`tradingagents/recommendation/industry_mapper.py`)

**功能：** 将主题关键词映射到申万行业，再映射到具体股票

**LLM增强（v0.2.0）：**
- 新增 `map_theme_to_industries_llm()` 方法：LLM动态分析主题与行业关联度
- Hybrid映射策略：先关键词匹配，失败时自动调用LLM fallback
- 支持不在硬编码映射表中的新主题（如量子计算、脑机接口等）

**核心方法：**
- `map_theme_to_industries(theme_name, keywords, use_llm_fallback)` - Hybrid映射
- `map_theme_to_industries_llm(theme_name, keywords)` - 纯LLM映射
- `find_stocks_for_theme(theme, screened_stocks, max_per_theme)` - 主题→股票

**内置映射表：** `THEME_TO_INDUSTRIES` 包含100+常见主题

**匹配策略：**
- 关键词灵活匹配（解决申万vs证监会分类差异）
- 复合行业名拆分匹配（如"通信设备"→"通信"+"设备"）
- LLM语义分析（当关键词完全无法匹配时触发）

---

### 4. DailyRecommender (`tradingagents/recommendation/daily_recommender.py`)

**功能：** 每日推荐整合器

**核心方法：**
- `generate_recommendations(trade_date, max_themes, max_stocks_per_theme, min_amount, with_deep_analysis)`
- `run_light_analysis(stock_code, trade_date)` - 轻量分析（市场+新闻分析师）

**流程：**
1. 提取今日主题
2. 篛选当日涨幅股票
3. 主题→股票映射
4. 可选：轻量分析验证

---

### 5. WeeklyRecommender (`tradingagents/recommendation/weekly_recommender.py`)

**功能：** 每周深度推荐

**核心方法：**
- `get_weekly_news(week_start, days)` - 汇聚一周新闻
- `extract_weekly_themes(week_start, max_themes)` - 周度主题提取
- `run_full_analysis(stock_code, trade_date)` - 完整分析（全部4分析师）
- `generate_recommendations(...)` - 完整pipeline

**特点：**
- 更高筛选门槛（周涨幅≥5%, 成交额≥5亿）
- 完整TradingAgentsGraph分析
- 周度视角的主题置信度加成

---

## 数据接口新增

### akshare_screening.py (`tradingagents/dataflows/akshare_screening.py`)

**新增接口：**
- `get_a_share_spot_sina()` - A股实时行情（Sina数据源）
- `screen_stocks()` - 多因子筛选
- `get_top_gainers(top_n)` - 涨幅榜
- `get_stock_daily_sina(code)` - 单股日线数据

### tushare_screening.py (`tradingagents/dataflows/tushare_screening.py`)

**新增接口（需高权限）：**
- `get_daily_basic()` - 每日基本面指标
- `get_moneyflow()` - 资金流向
- `get_limit_list()` - 涨跌停列表
- `screen_stocks_tushare()` - Tushare筛选

---

## CLI 命令

### 命令组：`python -m cli.main recommend`

#### 1. `recommend daily`

每日股票推荐

```bash
python -m cli.main recommend daily [--date YYYY-MM-DD] [--themes N] [--stocks N] [--amount AMOUNT] [--analyze] [--output FILE] [--json]
```

**参数：**
- `--date` / `-d`: 交易日期，默认今天
- `--themes` / `-t`: 最大主题数量，默认5
- `--stocks` / `-s`: 每主题最大股票数，默认5
- `--amount` / `-a`: 最小成交额（元），默认1亿
- `--analyze`: 启用深度分析验证（市场+新闻分析师）
- `--output` / `-o`: 输出文件路径
- `--json`: JSON格式输出

#### 2. `recommend weekly`

每周深度推荐

```bash
python -m cli.main recommend weekly [--week YYYY-MM-DD] [--themes N] [--stocks N] [--amount AMOUNT] [--analyze N] [--output FILE] [--json]
```

**参数：**
- `--week` / `-w`: 周起始日期，默认本周一
- `--analyze`: 最多分析股票数量，默认10

#### 3. `recommend themes`

仅显示热点主题

```bash
python -m cli.main recommend themes [--date YYYY-MM-DD] [--limit N]
```

#### 4. `recommend top`

仅显示涨幅榜

```bash
python -m cli.main recommend top [--amount AMOUNT] [--top N]
```

---

## Web API 接口

### 路由：`/api/recommend/*`

所有接口已注册到现有FastAPI应用。

#### 1. `GET /api/recommend/daily`

每日推荐

**参数：**
- `trade_date`: 交易日期
- `max_themes`: 最大主题数（默认5）
- `max_stocks`: 每主题最大股票数（默认5）
- `min_amount`: 最小成交额（默认1亿）
- `with_analysis`: 是否深度分析（默认false）

**返回：**
```json
{
  "trade_date": "2026-05-10",
  "themes": [...],
  "stocks": {"主题名": [股票列表]},
  "analysis": {},
  "summary": "Markdown报告"
}
```

#### 2. `GET /api/recommend/weekly`

每周推荐

**参数：**
- `week_start`: 周起始日期
- `max_themes`, `max_stocks`, `min_amount`, `max_analysis`

#### 3. `GET /api/recommend/themes`

热点主题

**参数：**
- `trade_date`, `limit`

#### 4. `GET /api/recommend/top`

涨幅榜

**参数：**
- `min_amount`, `top_n`

#### 5. `GET /api/recommend/screen`

股票筛选

**参数：**
- `min_change_pct`, `max_change_pct`, `min_amount`, `top_n`

---

## 推荐结果持久化

推荐结果自动保存到SQLite数据库，下次打开页面自动显示上一次结果。

**新增功能：**
- 进入 `/recommend` 页面自动加载上次推荐结果
- 每种模式（每日/每周/涨幅榜）独立保存
- 点击"重新生成"按钮强制更新
- 支持查看历史记录列表

**新增API：**
- `GET /api/recommend/latest` - 获取所有模式缓存结果
- `GET /api/recommend/latest/{mode}` - 获取指定模式缓存结果
- `GET /api/recommend/history` - 查看历史记录列表
- `refresh=true` 参数 - 强制重新生成（忽略缓存）

**数据库位置：** `web/backend/recommend_history.db`

**新增文件：**

| 文件 | 说明 |
|------|------|
| `web/backend/recommend_history_manager.py` | 推荐历史管理器 |

---

## Web 前端页面

### 路由：`/recommend`

新增推荐页面，集成到现有Vue.js前端框架。

**页面结构：**
- **三种模式Tab：** 每日推荐 / 每周深度 / 涨幅榜
- **参数配置区：** 日期、主题数、股票数、成交额阈值
- **深度分析开关：** 每日模式可选启用分析验证
- **热点主题卡片：** 显示主题名称、置信度、关键词
- **推荐股票表格：** 按主题分组，显示代码、价格、涨幅、行业
- **决策信号：** 深度分析后显示买卖决策和置信度
- **股票代码链接：** 点击跳转到个股分析页面

**前端文件变更：**

| 文件 | 操作 | 说明 |
|------|------|------|
| `web/frontend/src/views/RecommendView.vue` | 新建 | 推荐页面主组件 |
| `web/frontend/src/api.js` | 编辑 | 新增推荐API调用 |
| `web/frontend/src/router.js` | 编辑 | 新增/recommend路由 |
| `web/frontend/src/App.vue` | 编辑 | 导航栏新增推荐链接 |

**使用方式：**
1. 启动后端：`python -m web.backend.app` 或 `uvicorn web.backend.app:app`
2. 启动前端：`cd web/frontend && npm run dev`
3. 访问：`http://localhost:5173/recommend`

---

## 使用指南

### CLI命令行方式

```bash
# 每日推荐（轻量）
python -m cli.main recommend daily --themes 5 --stocks 5

# 每日推荐 + 深度分析验证
python -m cli.main recommend daily --analyze

# 每周深度推荐
python -m cli.main recommend weekly --week 2026-05-04

# 仅查看涨幅榜
python -m cli.main recommend top --top 20 --amount 5e8
```

### Web界面方式

1. **启动服务：**
   ```bash
   # 后端
   uvicorn web.backend.app:app --port 8000
   
   # 前端开发模式
   cd web/frontend && npm run dev
   
   # 或使用构建后的静态文件（后端自动服务）
   cd web/frontend && npm run build
   uvicorn web.backend.app:app --port 8000
   ```

2. **访问页面：**
   - 打开浏览器访问 `http://localhost:8000`
   - 点击导航栏"推荐"按钮
   - 或直接访问 `http://localhost:8000/recommend`

3. **页面操作：**
   - 选择模式：每日推荐 / 每周深度 / 涨幅榜
   - 设置参数：日期、主题数、成交额阈值
   - 点击"生成推荐"按钮
   - 查看热点主题卡片和推荐股票表格
   - 点击股票代码跳转到个股分析页面

### API接口方式

```bash
# 获取每日推荐
curl "http://localhost:8000/api/recommend/daily?max_themes=3&max_stocks=5"

# 获取涨幅榜
curl "http://localhost:8000/api/recommend/top?top_n=10&min_amount=500000000"

# 获取每周推荐
curl "http://localhost:8000/api/recommend/weekly?week_start=2026-05-04"
```

---

## 测试验证

### 单元测试结果

| 测试项 | 结果 | 说明 |
|--------|------|------|
| Module Imports | ✅ | 所有5个类导入成功 |
| StockScreener | ✅ | get_top_gainers(10)返回10条, screen()返回20条 |
| ThemeExtractor | ✅ | 新闻获取正常, 主题提取含fallback |
| IndustryMapper | ✅ | 主题→行业映射正确, 匹配5只股票 |
| DailyRecommender | ✅ | 生成完整报告(3主题, 6只股票) |
| WeeklyRecommender | ✅ | 汇聚周新闻正常(周末无数据) |
| CLI Commands | ✅ | daily/top命令输出正确 |
| Web API Router | ✅ | 5个endpoint注册成功 |
| Full Web App | ✅ | 38个路由, 5个推荐路由 |
| CLI Help | ✅ | 4个子命令显示正确 |

### 集成测试示例

```bash
# 每日推荐
$ python -m cli.main recommend daily --themes 2 --stocks 2

每日股票推荐 - 2026-05-10

今日热点主题
┃ AI算力硬件基础设施    │ 92%    │ 算力网, 数据中心, GPU        │
┃ 存储芯片产业链        │ 88%    │ HBM, DRAM, NAND             │

推荐股票

AI算力硬件基础设施
┃ sz002281 │ 光迅科技 │ 180.72 │ 10.00%
┃ sh600498 │ 烽火通信 │ 57.00  │ 10.00%
```

---

## 技术亮点

1. **LLM幻觉规避：** 主题提取禁止输出股票代码，完全由数据驱动匹配
2. **Fallback机制：** LLM失败时自动切换关键词匹配
3. **行业分类适配：** 灵活关键词匹配解决申万vs证监会差异
4. **复用现有架构：** TradingAgentsGraph轻量/完整模式验证
5. **数据源容错：** eastmoney屏蔽→Sina替代
6. **新闻数据聚合（v0.2.0）：** cls快讯 + major_news深度 + cctv政策，分段获取避免1500条上限
7. **LLM动态行业映射（v0.2.0）：** Hybrid策略，关键词匹配失败时自动调用LLM语义分析
8. **三层新闻接口复用（v0.2.0）：** 推荐系统新闻获取复用新闻分析师的分段获取逻辑

---

## 已知限制

1. **LLM API依赖：** 主题提取需配置有效的API Key
2. **Tushare权限：** daily_basic/moneyflow/limit_list需600+积分
3. **Eastmoney屏蔽：** 网络问题导致部分akshare接口不可用，已切换Sina
4. **行业分类API延迟：** 50只股票申万分类查询约需20秒（未优化）

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `tradingagents/recommendation/__init__.py` | 新建 | 模块入口，导出5个类 |
| `tradingagents/recommendation/theme_extractor.py` | 新建+编辑 | LLM主题提取 + 新闻获取改进 |
| `tradingagents/recommendation/stock_screener.py` | 新建 | 多因子筛选 |
| `tradingagents/recommendation/industry_mapper.py` | 新建+编辑 | 主题→行业→股票映射 + LLM增强 |
| `tradingagents/recommendation/daily_recommender.py` | 新建+编辑 | 每日推荐整合器 |
| `tradingagents/recommendation/weekly_recommender.py` | 新建 | 每周深度推荐 |
| `tradingagents/dataflows/akshare_screening.py` | 新建 | Sina数据源筛选 |
| `tradingagents/dataflows/tushare_screening.py` | 新建 | Tushare筛选接口 |
| `tradingagents/dataflows/interface.py` | 编辑 | 注册筛选接口 |
| `tradingagents/dataflows/akshare.py` | 编辑 | 更新导入 |
| `cli/commands/recommend.py` | 新建 | CLI recommend命令组 |
| `cli/main.py` | 编辑 | 导入recommend命令 |
| `web/backend/recommend_router.py` | 新建 | FastAPI推荐路由 |
| `web/backend/app.py` | 编辑 | 注册recommend_router |
| `web/frontend/src/views/RecommendView.vue` | 新建 | Vue推荐页面 |
| `web/frontend/src/api.js` | 编辑 | 新增推荐API |
| `web/frontend/src/router.js` | 编辑 | 新增/recommend路由 |
| `web/frontend/src/App.vue` | 编辑 | 导航栏新增链接 |
| `web/backend/recommend_history_manager.py` | 新建 | 推荐历史管理器 |

---

## 后续改进方向

1. **资金流向因子：** 集成tushare moneyflow数据（需600+积分）
2. **北向资金因子：** 北向资金增持股票加分
3. **动态评分权重：** 根据市场环境调整涨幅/成交额权重
4. **行业预加载：** 启动时预加载全市场申万分类到缓存
5. **实时推送：** Web UI增加推荐结果实时更新

---

## 版本记录

- **v0.1.0** (2026-05-10): 完成股票推荐系统核心实现
  - ThemeExtractor + StockScreener + IndustryMapper
  - DailyRecommender + WeeklyRecommender
  - CLI 4个命令 + Web API 5个endpoint
  - 深度分析集成（Phase 5）

- **v0.2.0** (2026-05-10): 新闻获取和数据驱动层优化
  - 新增 `get_recommendation_news` 接口，聚合cls+major_news+cctv
  - 复用三层新闻架构的分段获取逻辑（6h/12h分段）
  - 每日推荐look_back_days=1，每周推荐look_back_days=7
  - IndustryMapper新增LLM动态映射fallback
  - Hybrid策略：关键词匹配失败时自动调用LLM语义分析

---

**文档作者：** Claude Code Agent
**生成时间：** 2026-05-10