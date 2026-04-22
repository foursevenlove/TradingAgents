# TradingAgents Web UI

基于 FastAPI + Vue3 的 Web 界面，用于在浏览器中发起 AI 股票分析、实时观看多 Agent 协作过程、查看历史记录。

## 目录结构

```
web/
├── backend/          # FastAPI 后端
│   ├── app.py        # FastAPI 入口 + 静态文件服务
│   ├── router.py     # API 路由
│   ├── models.py     # Pydantic schemas
│   ├── task_manager.py   # 任务管理（内存 + SQLite）
│   ├── stream_adapter.py # LangGraph chunk -> SSE event
│   └── config.py     # Web 服务配置
├── frontend/         # Vue3 + Vite + TailwindCSS
│   ├── src/
│   │   ├── views/    # 页面视图
│   │   ├── components/  # 可复用组件
│   │   ├── stores/   # 状态管理
│   │   ├── api.js    # API 封装
│   │   └── router.js # 前端路由
│   └── package.json
└── README.md
```

## 快速启动

### 一键启动（推荐）

```bash
chmod +x scripts/start_web.sh
./scripts/start_web.sh
```

然后打开浏览器访问 http://localhost:8000

### 手动启动

1. 安装依赖：
```bash
pip install fastapi uvicorn
```

2. 构建前端（可选，用于生产访问根路径）：
```bash
cd web/frontend
npm install
npm run build
cd ../..
```

3. 启动服务：
```bash
uvicorn web.backend.app:app --reload --port 8000
```

### 开发模式

前后端独立开发：

```bash
# 终端1: 启动后端
uvicorn web.backend.app:app --reload --port 8000

# 终端2: 启动前端 dev server
cd web/frontend
npm install
npm run dev
```

前端 dev server 运行在 http://localhost:5173，已通过 Vite proxy 转发 `/api` 到后端。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze/start` | 启动分析 |
| GET | `/api/analyze/{task_id}/events` | SSE 流式事件 |
| GET | `/api/analyze/{task_id}/result` | 完整结果 |
| GET | `/api/analyze/{task_id}/status` | 任务状态 |
| GET | `/api/history` | 历史列表 |
| GET | `/api/history/{task_id}` | 历史详情 |
| GET | `/api/config` | 系统配置 |

## SSE Event 类型

- `started` - 分析开始
- `agent_start` - Agent 开始执行
- `agent_output` - Agent 输出内容
- `agent_end` - Agent 执行结束
- `tool_call` - 工具调用
- `tool_result` - 工具执行结果
- `debate_speech` - 辩论发言
- `debate_judge` - 裁判决策
- `trader_plan` - 交易员计划
- `final_decision` - 最终交易决策
- `completed` - 分析完成
- `failed` - 分析失败

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TRADINGAGENTS_WEB_HOST` | `0.0.0.0` | 监听地址 |
| `TRADINGAGENTS_WEB_PORT` | `8000` | 监听端口 |
| `TRADINGAGENTS_WEB_DB` | `web/tasks.db` | SQLite 数据库路径 |

## 验证步骤

1. 启动服务后访问 http://localhost:8000
2. 输入股票代码如 `600000.SH`，点击"开始分析"
3. 观察左侧 Agent 流水线逐步变绿
4. 右侧实时显示 LLM 输出和工具调用
5. 辩论环节显示多方/空方对话气泡
6. 完成后查看报告页，显示 BUY/SELL/HOLD 决策卡片
7. 历史记录页能查看本次分析
