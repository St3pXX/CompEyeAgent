# Phase 1.5 在线产品 Demo 执行计划

**目标**：把 Phase 1 已跑通的 CrewAI 竞品分析链路包装成可在线访问、可实时观察、可持续扩展的产品 Demo。

Phase 1.5 不重写 Agent 核心链路，优先完成 API 化、运行持久化、SSE 事件流、独立 Web App 和云端部署。所有接口按 Phase 2/3 可扩展形态设计，后续接入 DAG、Scratchpad、Run Inspector、MCP、飞书/钉钉时不重做前端主结构。

## 1. 范围边界

### 本阶段必须完成

- FastAPI API 层
- Run / Event / Artifact / Source 数据契约
- SQLite Run Store
- `runner.py` 后台执行封装
- `progress_callback` 写入事件流
- SSE 实时事件接口
- React / Vite Web App
- `/demo` 全屏任务创建页
- `/dashboard/:run_id` Agent 协作过程可视化
- `/reports/:run_id` 报告详情页
- FastAPI 托管前端静态资源
- 本地与云端部署文档

### 本阶段只预留接口

- DAG Planner
- Scratchpad 文件系统
- Run Inspector 深度下钻
- Trace / Metrics 详细链路
- PostgreSQL / Redis
- MCP Server
- 飞书 / 钉钉机器人
- 权限系统
- 企业工作区

## 2. 核心对象

Phase 1.5 之后，前后端统一围绕四类对象展开：

| 对象 | 说明 | 当前实现 |
|------|------|----------|
| Run | 一次竞品分析任务 | 已实现 |
| Event | Agent 执行事件 | 已实现 |
| Artifact | 报告、Brief、Verifier JSON、Provenance 等产物 | 已实现 |
| Source | 来源证据 | 已建表和接口，内容提取待补充 |

## 3. API Contract

### 已实现基础接口

```text
GET  /health
POST /api/runs
GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events
GET  /sse/runs/{run_id}
GET  /api/runs/{run_id}/artifacts
GET  /api/artifacts/{artifact_id}
GET  /api/runs/{run_id}/sources
POST /api/runs/{run_id}/cancel
POST /api/runs/{run_id}/retry
```

### 已预留扩展接口

```text
GET /api/runs/{run_id}/dag
GET /api/runs/{run_id}/scratchpad
GET /api/runs/{run_id}/inspector
GET /api/runs/{run_id}/trace
```

这些接口 Phase 1.5 先返回空态数据，Phase 2 接入真实 DAG、Scratchpad 和 Trace 时保持路径与响应入口不变。

## 4. 数据模型

### Run 状态

```text
queued -> running -> passed
queued -> running -> needs_review
queued -> running -> failed
queued -> running -> cancelled
```

### Event 类型

```text
run.created
run.started
agent.started
agent.progress
agent.completed
verifier.issue
artifact.ready
run.completed
run.failed
run.cancelled
```

### Artifact 类型

```text
brief_json
report_markdown
verifier_json
provenance_index
```

## 5. 实现顺序与进度

| 顺序 | 任务 | 状态 | 说明 |
|------|------|------|------|
| 1 | 定义 Schema / API Contract | 已完成 | `models/schema.py` 已新增 Run、Event、Artifact、Source、CreateRunRequest、RunDetailResponse |
| 2 | 支持自定义分析维度 | 已完成 | `Dimension.name` 已从固定 Literal 改为开放字符串 |
| 3 | 实现 SQLite Run Store | 已完成 | `storage/run_store.py` 已支持 runs、events、artifacts、sources |
| 4 | 实现 FastAPI 基础接口 | 已完成 | `api_app.py` 已提供基础接口、SSE 接口和扩展空态接口 |
| 5 | 接入后台执行 | 已完成 | `services/run_service.py` 已用 BackgroundTasks 调用 `run_analysis` |
| 6 | 接入 `progress_callback` | 已完成 | Agent 进度会写入 `agent_events` |
| 7 | 写入报告产物 | 已完成 | 运行完成后写入 brief、report、verifier artifact |
| 8 | 来源索引提取 | 已完成 | 从报告 Markdown 提取 URL，写入 `source_references`，并生成 `provenance_index` artifact |
| 9 | React / Vite 前端骨架 | 已完成 | `frontend/` 已建立 `/demo`、`/dashboard/:run_id`、`/reports/:run_id` 路由骨架 |
| 10 | Demo 页面 | 已完成 | 对话式需求澄清页已接 `POST /api/runs`，可用澄清后的 brief 创建真实任务并跳转 Dashboard |
| 11 | Dashboard 页面 | 已完成 | 已接 `GET /api/runs/{run_id}` 和 `/sse/runs/{run_id}`，可用真实事件更新 Agent 状态、时间线和报告入口 |
| 12 | Report 页面 | 已完成 | 已接真实 artifacts / sources，展示 Markdown 报告、Verifier JSON、Input Brief、来源索引并支持下载 |
| 13 | 前后端同服务部署 | 已完成 | FastAPI 已托管 `frontend/dist` 静态资源，并支持 React 路由刷新回退到 `index.html` |
| 14 | 云端部署 | 待开始 | 配置环境变量、运行数据目录和启动命令 |
| 15 | README / DESIGN 同步 | 待开始 | 更新在线体验、启动方式和 Phase 1.5 进度 |

## 6. 当前代码落点

```text
api_app.py                 FastAPI 入口
models/schema.py           API contract 与领域数据模型
services/run_service.py    创建任务、执行任务、写入事件和产物
storage/run_store.py       SQLite 持久化适配器
requirements.txt           FastAPI / Uvicorn 依赖
.gitignore                 忽略 data/ 本地运行库
```

## 7. 验收标准

### 后端验收

- `GET /health` 返回 200
- `GET /openapi.json` 正常生成 OpenAPI
- `POST /api/runs` 能创建任务并返回 `run_id`
- 任务执行过程能写入 `agent_events`
- `GET /sse/runs/{run_id}` 能实时推送事件
- 任务完成后能查询 report、brief、verifier artifacts
- 页面刷新后历史 run 仍可查询

### 前端验收

- 用户可从 `/demo` 创建真实分析任务
- 创建成功后自动进入 `/dashboard/:run_id`
- Dashboard 能实时展示 Agent 执行过程
- 报告生成后可以进入 `/reports/:run_id`
- Report 页面可直接刷新访问
- 前端不写死 CrewAI 内部实现，只消费 Run / Event / Artifact / Source

### 部署验收

- 本地可用 `uvicorn api_app:app` 启动
- 前端 build 可由 FastAPI 同服务托管
- 云端环境变量可配置
- `data/` 运行目录可持久化或挂载

## 8. 后续工程约束

- 前端页面结构按最终信息架构一次设计，Phase 2 只补数据，不重做 Dashboard。
- 后端接口路径保持稳定，新增能力优先扩展响应 payload，不破坏已有字段。
- SQLite 只作为 Phase 1.5 适配器，业务代码不得直接依赖 sqlite API。
- `runner.py` 当前保持兼容，后续替换为 Coordinator / DAG 时继续复用 Run Store 和 SSE contract。
