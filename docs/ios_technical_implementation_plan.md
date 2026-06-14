# iOS AI 股票分析助手技术实施计划

版本：v0.1  
日期：2026-05-21  
关联文档：

- `docs/ios_ai_investment_advisor_prd.md`
- `docs/ios_mvp_scope_roadmap.md`
- `docs/ios_mvp_failure_risk_assessment.md`
- `docs/ios_subscription_pricing_cost_model.md`

## 1. 总体目标

1 个月内交付 iOS MVP，跑通以下核心链路：

用户打开 App -> 确认风险提示 -> 搜索 A 股 -> 查看行情/新闻/公告摘要 -> 发起 AI 问诊 -> 查看结构化结论和完整报告 -> 保存报告或加入持仓 -> 查看额度和订阅权益。

技术拆分为五个模块：

- iOS 端
- 后端
- AI 分析链路
- 数据源
- 订阅支付

MVP 技术原则：

- 先做“AI 股票分析助手”，避免产品和接口命名使用强投顾表达。
- 先做轻量问诊闭环，再接完整多智能体深度流程。
- 所有 AI 结论必须结构化、可校验、可追踪。
- AkShare/Tushare 仅作为研发和封闭内测数据源，不作为商业发布授权依据。
- 真实 IAP 扣费作为 P1，MVP P0 先完成权益、额度、订阅页和购买状态抽象。

## 2. 模块一：iOS 端

### 目标

提供可测试的移动端主路径，优先保证搜索、问诊、报告、持仓、额度展示完整可用。

### 技术选型

- SwiftUI。
- Swift Concurrency：`async/await` 调用后端 API。
- StoreKit 2：订阅支付 P1 接入。
- Keychain 或本地安全存储：保存匿名设备 ID、风险确认状态、登录 token。
- 本地缓存：可用 SwiftData 或 SQLite，MVP 可先用轻量本地存储。

### P0 页面

- 风险提示页：首次进入必须确认。
- 首页：搜索框、最近问诊、自选入口、剩余额度。
- 股票搜索页：代码/名称搜索、空状态、错误状态。
- 股票详情页：价格、涨跌幅、数据更新时间、新闻/公告摘要。
- AI 问诊加载页：展示阶段进度、超时和取消。
- 问诊结果页：结论倾向、信心分数、参考区间、短中长期观点、核心理由、主要风险、反方观点、数据来源、完整报告。
- 额度/订阅权益页：Free / Pro / Premium 对比、额度耗尽提示。
- 持仓页：手动添加、编辑、删除持仓；对持仓股票发起问诊。
- 历史报告页：最近报告列表和详情。

### P0 客户端模型

- `UserProfile`：用户 ID、风险确认状态、当前订阅档位。
- `QuotaStatus`：轻量问诊剩余次数、深度问诊剩余次数、刷新时间。
- `StockSummary`：ticker、name、market、latestPrice、changePercent、updatedAt。
- `StockDetail`：行情摘要、新闻摘要、公告摘要、数据新鲜度。
- `AnalysisRequest`：ticker、analysisMode、holdingContext、clientRequestId。
- `AnalysisReport`：结构化报告结果。
- `Holding`：ticker、name、quantity、costPrice、notes。
- `SubscriptionPlan`：planId、displayName、price、benefits、limits。

### P0 交互要求

- 问诊按钮必须在额度不足、风险未确认、数据严重缺失时禁用或降级。
- 问诊结果必须明确展示“分析参考，不构成投资建议或收益承诺”。
- AI 输出中的“买入/卖出/减仓”在 UI 上建议呈现为“分析倾向”，避免强命令式按钮。
- 深度报告生成超过 10 秒时显示进度；超过 60 秒给出后台完成提示或失败降级。

### iOS 验收

- iPhone 模拟器可完成搜索 -> 详情 -> 问诊 -> 报告。
- 断网、接口失败、额度耗尽、数据不足均有明确状态。
- 风险提示确认后才允许问诊。
- 报告页面不会展示未经校验的空字段或越界数值。

## 3. 模块二：后端

### 目标

在现有 FastAPI Web 后端基础上增加移动端 API 层，提供账号/设备识别、额度、报告、持仓、订阅状态、分析任务和审计日志能力。

当前已有可复用能力：

- `web/backend/router.py`：分析任务启动、状态、结果、SSE、token usage。
- `web/backend/watchlist_router.py`：股票搜索、自选股、批量分析。
- `web/backend/holdings_router.py`：持仓 CRUD。
- `web/backend/stream_adapter.py`：TradingAgentsGraph 执行和 SSE 事件适配。
- `tradingagents/utils/token_tracker.py`：LLM token 使用统计。

### P0 API

#### 用户和风险确认

- `POST /api/mobile/session`
  - 输入：设备 ID、App 版本、平台。
  - 输出：userId、sessionToken、riskAccepted、plan、quota。
- `POST /api/mobile/risk-ack`
  - 输入：风险提示版本、确认时间。
  - 输出：riskAccepted。

#### 股票和数据摘要

- `GET /api/mobile/stocks/search?query=&limit=`
  - 复用现有 `search_stocks` 能力。
- `GET /api/mobile/stocks/{ticker}/snapshot`
  - 输出：行情、新闻、公告、数据来源、更新时间、freshness。

#### 问诊

- `POST /api/mobile/analysis/start`
  - 输入：ticker、analysisMode、clientRequestId、holdingId 可选。
  - 输出：taskId、status、quotaAfterStart。
- `GET /api/mobile/analysis/{task_id}/status`
- `GET /api/mobile/analysis/{task_id}/result`
- `GET /api/mobile/analysis/{task_id}/events`
  - 可复用现有 SSE；iOS MVP 如 SSE 不稳定，可轮询 status/result。
- `GET /api/mobile/analysis/{task_id}/usage`
  - 用于内部成本分析，普通用户不展示明细。

#### 报告

- `GET /api/mobile/reports`
- `GET /api/mobile/reports/{report_id}`
- `POST /api/mobile/reports/{report_id}/feedback`
  - 输入：useful、credible、willingToPay、comment。

#### 持仓

- `GET /api/mobile/holdings`
- `POST /api/mobile/holdings`
- `PUT /api/mobile/holdings/{holding_id}`
- `DELETE /api/mobile/holdings/{holding_id}`

#### 额度和订阅

- `GET /api/mobile/quota`
- `GET /api/mobile/subscription/plans`
- `GET /api/mobile/subscription/status`
- `POST /api/mobile/subscription/intent`
  - MVP P0 用于记录点击和付费意愿。

P1 增加：

- `POST /api/mobile/subscription/apple/verify-receipt`
- `POST /api/mobile/subscription/apple/notifications`

### P0 数据表

- `mobile_users`
  - id、device_id_hash、created_at、last_seen_at、risk_ack_version、risk_ack_at。
- `mobile_entitlements`
  - user_id、plan、source、status、expires_at。
- `mobile_quotas`
  - user_id、date、light_used、deep_used、portfolio_used。
- `mobile_reports`
  - id、user_id、task_id、ticker、mode、summary_json、full_report、data_snapshot_json、model_usage_json、created_at。
- `mobile_feedback`
  - report_id、user_id、useful、credible、willing_to_pay、comment、created_at。
- `mobile_audit_logs`
  - user_id、event_type、payload_json、created_at。
- `subscription_events`
  - user_id、provider、event_type、product_id、transaction_id、raw_payload_json、created_at。

### 后端验收

- 额度扣减具备幂等性：同一个 `clientRequestId` 不重复扣额度。
- 分析任务失败时返还或标记额度，不产生重复扣减。
- 每份报告保存数据快照、模型 usage、风险确认状态。
- 可以按用户查询报告、反馈和消耗。

## 4. 模块三：AI 分析链路

### 目标

把现有 TradingAgents 多智能体能力包装成移动端可消费的两级分析链路：

- Light：低成本、低延迟、结构化输出，Free 默认。
- Deep：更完整分析，Pro/Premium 使用。

### P0 Light 链路

输入：

- ticker。
- 行情摘要。
- 新闻摘要。
- 公告摘要。
- 基础财务或指标摘要。
- 可选持仓上下文。

处理步骤：

1. 数据质量检查：行情、新闻、公告、更新时间。
2. 规则预处理：涨跌停、停牌、ST、交易时间、T+1、数据过旧。
3. 轻量模型综合分析。
4. 结构化 JSON 输出。
5. 程序化校验。
6. 合规表达过滤和降级。
7. 保存报告和审计日志。

建议模型：

- Free Light：qwen-turbo 非思考。
- Pro Light：qwen-turbo 或 deepseek-v4-flash。

### P1 Deep 链路

输入：

- Light 链路全部输入。
- 更长新闻/公告上下文。
- 技术面、基本面、消息面、资金面子报告。
- 可选多智能体辩论结果。

处理步骤：

1. 复用现有 `TradingAgentsGraph`，但移动端默认降低轮数。
2. `selected_analysts` 初始建议：`market`, `news`, `fundamentals`；`social` 可根据稳定性决定。
3. `max_debate_rounds` 默认 0 或 1。
4. `max_risk_discuss_rounds` 默认 0 或 1。
5. 用强模型生成最终结构化摘要。
6. 生成完整报告正文。

建议模型：

- Pro Deep：qwen-plus 思考或 deepseek-v4-flash。
- Premium Deep：qwen-plus 思考，必要时用更强模型最终总结。

### 结构化输出 Schema

```json
{
  "ticker": "600000.SH",
  "stock_name": "浦发银行",
  "analysis_mode": "light",
  "as_of": "2026-05-21T15:05:00+08:00",
  "stance": "neutral",
  "stance_label": "观望",
  "confidence": 64,
  "reference_ranges": {
    "entry": {"low": 0, "high": 0, "available": false, "reason": "数据不足或不适合给出区间"},
    "take_profit": {"low": 0, "high": 0, "available": false, "reason": "MVP 阶段弱化操作区间"},
    "stop_loss": {"low": 0, "high": 0, "available": false, "reason": "MVP 阶段弱化操作区间"}
  },
  "horizons": {
    "short_term": "偏中性",
    "swing": "偏谨慎",
    "mid_long_term": "需观察基本面改善"
  },
  "reasons": [
    {"dimension": "technical", "summary": "技术面摘要", "evidence": ["..."]},
    {"dimension": "fundamental", "summary": "基本面摘要", "evidence": ["..."]},
    {"dimension": "news", "summary": "消息面摘要", "evidence": ["..."]},
    {"dimension": "capital_flow", "summary": "资金面摘要", "evidence": ["..."]}
  ],
  "risks": ["..."],
  "counter_arguments": ["..."],
  "invalid_conditions": ["..."],
  "data_sources": [
    {"type": "quote", "vendor": "tushare", "updated_at": "...", "freshness": "delayed"}
  ],
  "compliance_disclaimer": "本内容仅为 AI 基于公开信息生成的分析参考，不构成投资建议或收益承诺。",
  "full_report": "..."
}
```

### 程序化校验

- `stance` 只能为：`positive`, `neutral`, `cautious`, `avoid`。
- `stance_label` 只能映射为：偏积极、观望、偏谨慎、规避。
- `confidence` 范围 0-100。
- 所有价格区间必须大于 0 且符合涨跌停、停牌、最新价上下文；无法校验则不展示。
- 必须有 risks、counter_arguments、data_sources。
- 禁止词命中时，自动降级为更保守表达或阻断报告发布。

### AI 链路验收

- 结构化输出解析成功率 >= 98%。
- 主要风险、反方观点、数据来源覆盖率 = 100%。
- 单次 Light 问诊 P95 小于 15 秒。
- 单次 Deep 问诊 P95 小于 90 秒。
- token usage 按 task_id、user_id、mode、model 记录。

## 5. 模块四：数据源

### 目标

为移动端问诊提供可追踪、可降级的数据快照。MVP 先用现有数据能力跑封闭内测，同时为商业发布预留正式授权数据源接口。

### 当前可复用模块

- `tradingagents/dataflows/akshare_stock.py`
- `tradingagents/dataflows/tushare_stock.py`
- `tradingagents/dataflows/akshare_news.py`
- `tradingagents/dataflows/tushare_news.py`
- `tradingagents/dataflows/interface.py`
- `tradingagents/market_rules/`

### P0 数据聚合服务

新增或整理服务层：

- `MobileStockSnapshotService`
  - 聚合行情、新闻、公告、数据来源、更新时间。
- `DataFreshnessEvaluator`
  - 输出 `realtime`, `delayed`, `stale`, `missing`, `mixed`。
- `DataSnapshotStore`
  - 保存每次报告使用的数据快照。
- `VendorHealthMonitor`
  - 记录接口成功率、耗时、失败原因。

### P0 数据要求

- 行情：最新价、涨跌幅、成交量或成交额、更新时间。
- 新闻：标题、来源、发布时间、URL 或来源标识。
- 公告：标题、来源、发布时间、URL 或来源标识。
- 基础指标：能支持核心理由即可，不追求完整财务报表。

### 数据降级规则

- 行情缺失：禁止生成带操作区间的报告。
- 新闻/公告缺失：允许生成报告，但必须声明“消息面数据不足”。
- 数据超过设定新鲜度：降低信心分数上限。
- 多数据时间不一致：报告必须展示 mixed freshness。
- 数据源失败：返回可解释错误，不让模型基于空数据猜测。

### 商业发布前闸门

- 明确行情、公告、新闻的可商用授权。
- 确认是否允许移动端展示、缓存、AI 分析加工和订阅收费。
- 建立数据供应商合同和 SLA。

### 数据源验收

- 同一 ticker snapshot API P95 小于 3 秒。
- snapshot 中每个字段都有 vendor 和 updated_at。
- 数据源失败不会导致 AI 生成确定性强结论。
- 报告可回溯到生成时的数据快照。

## 6. 模块五：订阅支付

### 目标

MVP 建立权益系统和额度控制，真实 StoreKit 支付作为 P1 接入。即使暂不扣费，也要让后端从第一天按订阅模型管理能力。

### P0：权益和额度

计划：

- Free：每日 3 次轻量问诊，每周 1 次完整报告试用。
- Pro：每日 20 次轻量问诊，每日 3 次深度问诊。
- Premium：每日 50 次轻量问诊，每日 8 次深度问诊，每日 1 次持仓体检。

后端能力：

- `EntitlementService`：判断用户当前档位。
- `QuotaService`：检查、预扣、确认、返还额度。
- `PlanCatalogService`：返回 Free / Pro / Premium 权益。
- `SubscriptionIntentService`：记录订阅页曝光、点击和付费意愿。

额度扣减流程：

1. iOS 发起问诊，带 `clientRequestId`。
2. 后端检查风险确认和当前 plan。
3. 后端预扣对应额度。
4. 分析任务创建。
5. 成功后确认消耗。
6. 失败或取消时按规则返还或标记失败。

### P1：Apple IAP

iOS：

- StoreKit 2 获取商品。
- 展示订阅组：Pro Monthly、Pro Yearly、Premium Monthly、Premium Yearly。
- 发起购买、恢复购买、管理订阅入口。
- 本地只做展示和临时状态，最终权限以后端校验为准。

后端：

- 校验 Apple transaction。
- 接入 App Store Server Notifications。
- 存储 transaction_id、original_transaction_id、product_id、expires_at、revocation。
- 更新 `mobile_entitlements`。

### 订阅支付验收

P0：

- 额度耗尽后展示订阅权益页。
- 订阅权益页不承诺收益，不售卖“更准买卖点”。
- 所有问诊都经过额度服务。
- 可以统计订阅页曝光、点击和付费意愿。

P1：

- 沙盒订阅购买、续订、取消、恢复购买可跑通。
- 后端能根据 Apple transaction 更新权益。
- 订阅降级/过期后额度按 Free 生效。

## 7. 跨模块接口约定

### 问诊模式

- `light`：轻量问诊，低成本、短报告。
- `deep`：深度问诊，完整报告。
- `portfolio`：持仓体检。

### 用户档位

- `free`
- `pro`
- `premium`
- `internal_test`

### 报告状态

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`
- `blocked_by_compliance`
- `degraded_by_data_quality`

### 数据新鲜度

- `realtime`
- `delayed`
- `stale`
- `missing`
- `mixed`

## 8. 4 周实施排期

### 第 1 周：基础链路

iOS：

- 建 SwiftUI 工程。
- 完成风险提示、搜索、股票详情、问诊结果静态页面。
- 接入 session、search、snapshot、analysis start/status/result API。

后端：

- 新建 mobile router。
- 新增 session、risk ack、quota、plans API。
- 包装 mobile analysis start。
- 定义 report JSON schema。

AI 分析链路：

- 实现 Light 问诊原型。
- 输出固定 JSON。
- 加入禁止表达和基础校验。

数据源：

- 实现 snapshot 聚合。
- 保存数据来源和更新时间。

订阅支付：

- 定义 Free / Pro / Premium plan catalog。
- 额度服务最小版本。

### 第 2 周：主路径可用

iOS：

- 完成搜索、详情、问诊、报告完整交互。
- 加入加载、失败、数据不足、额度不足状态。

后端：

- 报告保存。
- token usage 绑定 user_id、report_id。
- 事件埋点 API。

AI 分析链路：

- 完成结构化校验。
- 加入主要风险、反方观点、数据来源强制字段。
- 加入 A 股规则校验。

数据源：

- 做数据新鲜度判断。
- 建立 snapshot 缓存。
- 压测常用股票。

订阅支付：

- 额度预扣/确认/返还。
- 订阅页曝光和点击统计。

### 第 3 周：商业化和辅助路径

iOS：

- 完成订阅权益页。
- 完成持仓 CRUD。
- 完成历史报告。
- 完成报告反馈。

后端：

- 持仓与 mobile user 绑定。
- 历史报告列表和详情。
- 反馈 API。

AI 分析链路：

- 实现 Deep 问诊 P1 原型。
- 为 Pro/Premium 路由不同模型和额度。
- 输出成本估算。

数据源：

- 供应商健康监控。
- 数据失败降级策略固化。

订阅支付：

- StoreKit 2 沙盒接入评估。
- 如果排期允许，开始 Apple transaction 校验。

### 第 4 周：内测和发布准备

iOS：

- TestFlight 包。
- 修复主路径崩溃、慢加载、空状态。
- 完成基础可用性测试。

后端：

- 审计日志检查。
- 成本统计看板。
- 用户反馈导出。

AI 分析链路：

- 20-30 只股票评测集。
- 高风险输出复盘。
- 调整 prompt 和校验规则。

数据源：

- 数据质量报告。
- 商业数据源候选清单。

订阅支付：

- P0 保持权益和额度验证。
- P1 决定是否进入真实 IAP 开发和审核准备。

## 9. 关键依赖和阻塞项

- 合规主体和产品命名确认。
- A 股商业数据源授权确认。
- iOS 开发者账号、Bundle ID、App Store Connect 权限。
- StoreKit 沙盒测试账号。
- 生产可用的 LLM API key 和预算上限。
- 移动端用户身份策略：匿名设备 ID、手机号、Apple 登录三选一。

## 10. 测试计划

### 后端测试

- `conda run -n tradingagents pytest test_*.py`
- 新增 mobile API 单元测试。
- 新增 quota 幂等和失败返还测试。
- 新增 report schema 校验测试。
- 新增数据降级测试。

### AI 链路测试

- 20-30 只股票评测集。
- 结构化输出解析率。
- 禁止词命中和降级测试。
- token usage 和耗时统计。

### iOS 测试

- iPhone SE、标准 iPhone、Pro Max 三种尺寸。
- 断网、慢网、后端 500、超时。
- 首次风险确认、额度耗尽、报告失败、历史报告为空。
- TestFlight 内测反馈。

### 订阅测试

- P0：权益页、额度扣减、额度耗尽、付费意愿事件。
- P1：StoreKit 沙盒购买、恢复购买、过期、取消、降级。

## 11. 第一版不做

- 真实交易下单。
- 券商账户绑定。
- 价格/公告/新闻推送提醒。
- 自动调仓。
- 港股、美股、ETF 完整支持。
- 社区、排行榜、跟单。
- PDF/图片导出。
- 复杂运营后台。

## 12. MVP 完成定义

满足以下条件才算 iOS MVP 可进入 50-100 人种子测试：

- iOS 主路径可跑通且无阻塞性崩溃。
- 后端能按用户管理风险确认、额度、报告和反馈。
- Light 问诊结构化输出稳定，且有风险、反方观点、数据来源。
- 每次报告可追踪数据快照、模型 usage 和审计日志。
- 订阅权益页和额度控制可用。
- 合规文案经过至少一轮人工审查。
- 数据源授权状态已明确标记为研发/内测/商业。
