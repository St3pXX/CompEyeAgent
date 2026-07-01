<p align="center">
  <h1 align="center">CompEye Agent</h1>
  <p align="center">AI 竞品分析智能体系统 · <strong>采集 → 分析 → 质检 → 报告</strong>，全流程自动化，每条结论可溯源。</p>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
  <a href="https://github.com/St3pXX/CompEyeAgent"><img src="https://img.shields.io/badge/status-active-success" alt="Active"></a>
</p>

---

## 简介

传统竞品调研依赖人工搜索、整理、撰写，一次分析需数天。CompEye Agent 将这个过程自动化：你输入目标产品、竞品列表和分析维度，系统在几分钟内交付一份**带溯源标注的完整报告** — 每条结论附来源 URL 和原文片段，并由独立质检节点验证。

系统由 **LangGraph 编排**四个专职节点（采集 → 分析 → 撰写 → 质检），质检失败时自动重写一次。执行过程通过 SSE 实时推送到前端看板，LLM 调用链路由自托管 Langfuse 完整追踪。

## 核心特性

| 特性 | 说明 |
|---|---|
| **多节点协作** | 四节点线性流水线：collect / analyze / write / verify，每个节点职责单一、输入输出结构清晰 |
| **自动重写闭环** | verify 判定不合格时，自动触发一次 rewrite，无需人工干预 |
| **结论溯源** | 报告中每条结论强制附带 `[来源: URL]` 标注，末尾附 Provenance 索引表；规则层校验缺失则判失败 |
| **独立质检** | verify 节点使用专用模型，**不继承撰写者上下文**，主动发现逻辑矛盾、幻觉、缺失证据 |
| **实时事件流** | SSE 毫秒级推送节点进度到前端看板，支持断线重连、阶段状态推导 |
| **LLM 追踪** | 自托管 Langfuse 捕获所有 litellm 调用（提示词 / 输出 / token / 延迟），数据不出网 |
| **长期记忆** | ChromaDB + bge-base-zh-v1.5 语义向量存储，跨分析复用已验证事实 |
| **多入口** | Web App（React 19）/ CLI / MCP Server（Claude Code 集成）|
| **韧性设计** | 熔断器、节点超时、多模型降级、部分结果交付 |

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+（前端，可选）
- MiMo API Key（或任意 OpenAI 兼容端点）

### 安装

```bash
git clone https://github.com/St3pXX/CompEyeAgent.git
cd CompEyeAgent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，至少配置：

```bash
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=your_api_key_here
```

### CLI 运行

```bash
python main.py '{
  "productName": "飞书",
  "competitors": ["钉钉", "企业微信"],
  "dimensions": [
    {"name": "定价", "indicators": ["免费套餐", "付费套餐"]},
    {"name": "功能", "indicators": ["即时通讯", "文档协作"]}
  ],
  "analysisType": "SWOT"
}'
```

### API 服务

```bash
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

启动后访问：
- **API 文档**：`http://localhost:8000/docs`
- **Web App**：`http://localhost:8000`（需先 `cd frontend && npm ci && npm run build`）

### 一键体验

```bash
# 后端 + 前端一起启动（开发模式）
uvicorn api_app:app --reload &
cd frontend && npm ci && npm run dev
```

## 架构

```
用户入口（Web App / CLI / MCP）
        │
        ▼
 FastAPI ──→ EventBus ──→ SSE 实时推送
        │
        ▼
 Coordinator ──→ LangGraph StateGraph
                    │
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
collect_node    analyze_node     write_node
   │                │                │
   └────────────────┼────────────┬───┘
                    ▼            ▼
               verify_node    passed? ─→ END
                    │            │
                    ▼            │ (no)
              passed=False ──────┘
                    │
                    ▼
              rewrite_node ──→ verify_node
```

四个节点线性执行，状态通过 `AnalysisState` TypedDict 传递。`verify` 判定失败时，条件路由自动返回 `write_node` 重写一次（`retry_count < 1`）。每一步通过 SQLite checkpointer 持久化，支持断点续跑。

### 节点详解

| 节点 | 模型 | 输入 | 输出 | 说明 |
|---|---|---|---|---|
| **collect** | MiMo-V2.5 | 竞品列表 + 维度 | `collect_raw` (JSON) | 联网搜索 + Evidence Index 检索，每条数据附 source_references |
| **analyze** | MiMo-V2.5 | `collect_raw` | `analyze_findings` (JSON) | SWOT / 对比分析，每条结论附 provenance |
| **write** | MiMo-V2.5 | `analyze_findings` | `report` (Markdown) | 分维度报告 + `[来源: URL]` 标注 + Provenance 索引 |
| **verify** | MiMo-V2.5-Pro | `report` | `verifier_result` (JSON) | 独立质检，不继承撰写上下文 |
| **rewrite** | MiMo-V2.5 | `analyze_findings` + issues | `report` | 按质检意见重写，最多 1 次 |

## 项目结构

```
CompEyeAgent/
├── graph/                        # LangGraph 编排层
│   ├── build.py                  # StateGraph 构建 + checkpointer
│   ├── state.py                  # AnalysisState TypedDict
│   ├── nodes.py                  # 四节点函数 + rewrite
│   └── prompts.py                # 提示词模板
├── services/
│   ├── llm_client.py             # litellm 封装（统一 LLM 调用）
│   ├── web_search.py             # 联网搜索工具
│   ├── graph_node_executor.py    # 节点 → Coordinator 适配器
│   ├── coordinator_loop.py       # DAG 调度主循环
│   ├── coordinator_foundation.py # DAG / Scratchpad 状态管理
│   ├── run_service.py            # Run 生命周期
│   ├── event_bus.py              # 内存事件队列
│   ├── verification.py           # Provenance Guard + 质检解析
│   ├── llm_telemetry.py          # token 回调（Cost 页面数据源）
│   ├── langfuse_client.py        # Langfuse 集成
│   ├── resilience.py             # 熔断器 / 超时 / 降级
│   ├── evidence_service.py       # 证据注入 Collector 上下文
│   ├── evidence_extractor.py     # 关键词证据提取
│   ├── source_connectors.py      # Jina/NewsAPI/GitHub/RSS/Reddit
│   └── source_refresh.py         # 来源刷新
├── storage/
│   ├── protocols.py              # 存储抽象（Protocol）
│   ├── run_store.py              # SQLite: runs / events / artifacts
│   ├── coordinator_store.py      # SQLite: DAG / scratchpad
│   ├── source_store.py           # SQLite: sources / evidence
│   └── vector_store.py           # ChromaDB: 长期记忆
├── config/
│   ├── settings.py               # 环境变量 + LLM 工厂
│   ├── model_registry.py         # 多模型优先级降级
│   └── source_seeds.py           # 默认来源种子
├── models/
│   ├── schema.py                 # CompetitorInput / Run / Event / Artifact
│   ├── coordinator.py            # DAGNode / ScratchpadItem
│   ├── source_layer.py           # SourceSeed / EvidenceItem
│   └── provenance.py             # SourceRef / Provenance
├── frontend/                     # React 19 + TypeScript + Vite
│   └── src/pages/                # Demo / Dashboard / Report 等
├── tests/                        # pytest（137 个测试）
├── main.py                       # CLI 入口
├── api_app.py                    # FastAPI 入口
├── runner.py                     # 分析执行器（调用 LangGraph）
├── mcp_server.py                 # MCP Server（Claude Code 集成）
├── requirements.txt
└── README.md
```

## 配置参考

### 必填

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `MIMO_API_KEY` | MiMo API Key | `sk-xxx` |
| `MIMO_BASE_URL` | API 端点 | `https://api.xiaomimimo.com/v1` |

### 持久化

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `RUN_STORE_PATH` | `data/run_store.sqlite3` | 任务记录 + 事件 |
| `COORDINATOR_STORE_PATH` | `data/coordinator_store.sqlite3` | DAG 状态 + Scratchpad |
| `SOURCE_STORE_PATH` | `data/source_store.sqlite3` | 来源索引 |
| `COMPETEYE_CHECKPOINT_PATH` | `data/graph_checkpoints.sqlite3` | LangGraph 断点续跑 |
| `COMPETEYE_VECTOR_STORE_PATH` | `data/vector_store` | 长期记忆向量库 |

### 模型

| 环境变量 | 默认值 | 用途 |
|---------|--------|------|
| `COLLECTOR_MODEL` | `mimo-v2.5` | 采集 |
| `ANALYZER_MODEL` | `mimo-v2.5` | 分析 |
| `WRITER_MODEL` | `mimo-v2.5` | 撰写 |
| `VERIFIER_MODEL` | `mimo-v2.5-pro` | 质检 |
| `COMPETEYE_EMBEDDING_MODEL` | `BAAI/bge-base-zh-v1.5` | 向量 embedding |

### 可观测（可选）

| 环境变量 | 说明 |
|---------|------|
| `LANGFUSE_HOST` | Langfuse 实例地址 |
| `LANGFUSE_PUBLIC_KEY` | Langfuse 公钥 |
| `LANGFUSE_SECRET_KEY` | Langfuse 密钥 |

不配置 Langfuse 时系统正常运行，仅无 LLM 追踪。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/runs` | 创建分析任务 |
| `GET` | `/api/runs` | 查询任务列表 |
| `GET` | `/api/runs/:id` | 获取任务详情（含事件、产物、来源） |
| `GET` | `/api/runs/:id/events` | 获取事件列表 |
| `GET` | `/sse/runs/:id` | SSE 实时事件流 |
| `GET` | `/api/runs/:id/artifacts` | 获取产物（报告、质检结果） |
| `GET` | `/api/artifacts/:id` | 获取单个产物 |
| `GET` | `/api/runs/:id/sources` | 获取来源列表 |
| `GET` | `/api/runs/:id/dag` | 获取 DAG 视图 |
| `GET` | `/api/runs/:id/scratchpad` | 获取中间产物 |
| `POST` | `/api/runs/:id/cancel` | 取消任务 |
| `POST` | `/api/runs/:id/dag/:node/retry` | 重试单个节点 |
| `GET` | `/api/reviews` | 查询复核队列 |
| `POST` | `/api/reviews/:id/approve` | 审批通过 |
| `POST` | `/api/reviews/:id/reject` | 驳回 |
| `GET` | `/api/stats` | 运行统计 |
| `GET` | `/api/costs` | Token 使用统计 |
| `GET` | `/health` | 健康检查 |

## 测试

```bash
pytest
```

覆盖范围：
- **LLM 层**：litellm 封装 + 多模型降级（mocked）
- **Graph 层**：节点函数 + 条件路由 + 重写闭环（mocked）
- **编排层**：Coordinator + 事件双写 + DAG 同步（SQLite 隔离）
- **前端契约**：SSE 事件名 / 阶段 / DAG / artifacts 完整性
- **向量存储**：bge 语义检索 + fallback 维度兼容
- **韧性**：熔断器 / 超时 / 降级

## MCP Server

在 Claude Desktop / Claude Code 中接入：

```json
{
  "mcpServers": {
    "compeye": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {
        "MIMO_BASE_URL": "https://api.xiaomimimo.com/v1",
        "MIMO_API_KEY": "sk-xxx"
      }
    }
  }
}
```

暴露 9 个工具：`create_run` / `get_run` / `get_report` / `get_verification` / `list_runs` / `get_sources` / `get_scratchpad` / `cancel_run` / `retry_node`。

## 部署

完整部署说明见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。关键点：

- **持久化**：所有 `*_PATH` 环境变量必须指向持久卷（阿里云 NAS / 云盘），否则重启丢数据
- **Nginx**：SSE 需 `proxy_buffering off`
- **适用规模**：SQLite 适合单实例，多实例需升级 PostgreSQL（`storage/protocols.py` 已解耦，只需新增实现类）
- **Langfuse**：`docker-compose` 自托管，数据不出网

## 文档

| 文档 | 内容 |
|------|------|
| [docs/DESIGN.md](docs/DESIGN.md) | 完整架构设计、分阶段路线图 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 云部署说明 |
| [docs/MIGRATION.md](docs/MIGRATION.md) | CrewAI → LangGraph 迁移指南 |

## 许可证

MIT License © CompEye Agent
