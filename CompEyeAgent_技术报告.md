# CompEyeAgent 技术架构报告 — 面试准备手册

> **项目**：CompEyeAgent — AI 竞品分析 Agent 协作系统
> **技术栈**：Python 3.11+ / CrewAI / FastAPI / React 19 / ChromaDB / OpenTelemetry / Prometheus
> **规模**：后端 ~8000 行 + 前端 ~2000 行 · 145 个测试 · 4 个大版本 · 27 个子里程碑
> **最后更新**：2026 年 6 月

---

## 目录

- [一、项目总览](#一项目总览)
- [二、系统架构](#二系统架构)
- [三、Agent 编排与任务调度](#三agent-编排与任务调度)
- [四、数据层设计](#四数据层设计)
- [五、可靠性与韧性设计](#五可靠性与韧性设计)
- [六、可观测性体系](#六可观测性体系)
- [七、人工复核与权限](#七人工复核与权限)
- [八、前端工程](#八前端工程)
- [九、平台集成](#九平台集成)
- [十、测试与质量保障](#十测试与质量保障)
- [十一、面试高频问题集（74 题）](#十一面试高频问题集)
- [十二、技术决策记录](#十二技术决策记录)
- [十三、未来优化方向](#十三未来优化方向)

---

## 一、项目总览

### 1.1 项目定位与业务价值

CompEyeAgent 是面向产品、市场、战略和研发团队的 **AI 竞品分析工作台**。系统将传统需要数天的竞品调研流程自动化为分钟级的端到端分析任务。

**核心价值主张**：

1. **分析过程自动化**：将"目标产品 + 竞品列表 + 分析维度 + 重点指标"转化为可执行的多 Agent 任务链路。用户无需手动搜索、整理、撰写，系统自动完成从信息采集到报告交付的全流程。

2. **结论可追溯**：报告中的每条关键判断必须关联来源 URL、原文片段和 Provenance 索引。规则层守卫（Provenance Guard）会在报告交付前强制校验来源标注的完整性，缺失来源的结论会被标记为"待核实"或触发重写。

3. **执行过程可观测**：每个 Agent 的状态、产物、质检结果和重试动作都可以通过 SSE 实时事件流、Run Inspector 和 Prometheus 指标进行追踪、复盘和治理。

**与传统方式的对比**：

| 维度 | 传统方式 | CompEyeAgent |
|------|----------|-------------|
| 信息采集 | 人工搜索，手动整理 | Collector Agent 自动联网搜索 + 来源情报层预索引 |
| 结构化分析 | 依赖个人经验 | Analyzer Agent 标准化 SWOT/对比分析 |
| 报告撰写 | 人工撰写，耗时数天 | Writer Agent 自动生成 Markdown 报告 |
| 质量校验 | 主观判断 | Verifier Agent 独立质检 + Provenance Guard 规则校验 |
| 来源追溯 | 手动标注，容易遗漏 | 强制 `[来源: URL]` 标注 + Provenance 索引 |
| 可观测性 | 无 | SSE 事件流 + Prometheus + OTel 分布式追踪 |

### 1.2 系统边界与核心能力矩阵

| 能力 | 说明 | 对应组件 |
|------|------|----------|
| **多角色协作** | 采集、分析、撰写、质检四个专职 Agent 协同 | `crew/agents/` 下四个 Agent 定义 |
| **任务编排** | DAG 状态机调度器，支持节点级重试和依赖推进 | `services/coordinator_loop.py` |
| **交叉审查闭环** | 独立质检 Agent + Provenance Guard 规则引擎 | `services/verification.py` + `runner.py` |
| **结果溯源** | 工具层强制约束，每条结论附来源 URL + 原文片段 | Provenance Guard 三层校验 |
| **可观测性** | 三层指标：Prometheus + OTel 追踪 + SSE 事件 | `services/telemetry.py` |
| **韧性设计** | 熔断器/超时/部分结果/多模型降级 | `services/resilience.py` + `config/model_registry.py` |
| **长期记忆** | 向量存储 + 事实提取 + 跨 run 语义检索 | `storage/vector_store.py` + `services/memory_service.py` |
| **平台集成** | MCP Server 暴露工具给 Agent 工作台 | `mcp_server.py` |

### 1.3 项目规模与迭代历程

**代码规模**：
- 后端 Python：~8000 行（25 个模块）
- 前端 TypeScript：~2000 行（10 个文件）
- 测试：145 个（135 后端 pytest + 10 前端 vitest）
- 文档：6 个设计文档 + README + AGENTS.md + CLAUDE.md

**迭代历程**：

| 阶段 | 时间 | 核心交付 | 子里程碑数 |
|------|------|----------|-----------|
| Phase 1: MVP | 2026 年 5 月上旬 | CrewAI 四 Agent 链路 + Provenance Guard + CLI/Streamlit | 5 |
| Phase 1.5: 产品 Demo | 2026 年 5 月中旬 | FastAPI + React Web App + SSE + SQLite + Docker 部署 | 6 |
| Phase 2: 任务编排 | 2026 年 5 月下旬 ~ 6 月初 | DAG 调度器 + 逐节点执行 + EventBus + OTel | 8 |
| Phase 3: 企业级平台 | 2026 年 6 月 | 存储抽象 + 韧性 + 多模型 + 复核队列 + 长期记忆 + Dashboard + MCP | 8 |

**合计 27 个子里程碑，全部完成。**

---

## 二、系统架构

### 2.1 七层架构详解

系统按职责分为七个层次，每层独立演进，层间通过明确的接口交互：

**第一层：用户入口层**

三个入口点服务不同场景：
- **Web App**（React 19）：面向终端用户的可视化界面，包含 Demo 任务创建、Dashboard 实时追踪、Report 报告详情、Overview 概览统计、Review 复核队列、Cost 成本追踪六个页面。
- **CLI**（`main.py`）：面向脚本化批量执行，接受 JSON 参数，直接调用 `runner.run_analysis()`。
- **MCP Server**（`mcp_server.py`）：面向 Agent 工作台（Claude Code、Codex），通过 MCP 协议暴露 9 个工具。

**第二层：服务层**

- **FastAPI Gateway**（`api_app.py`）：统一 API 网关，提供 REST 端点（run CRUD、review、stats、costs）和 SSE 事件流。同时托管 React 前端静态文件，实现单服务部署。
- **SSE Event Stream**：通过 EventBus 内存队列实现毫秒级事件推送，自动回退到 SQLite 轮询兼容旧客户端。

**第三层：任务编排层**

- **Coordinator 主循环**（`coordinator_loop.py`）：DAG 状态机调度器，管理节点生命周期（pending → running → completed/failed/skipped），支持依赖推进和节点级重试。
- **EventBus**（`event_bus.py`）：基于 `asyncio.Queue` 的内存事件总线，通过 `loop.call_soon_threadsafe()` 桥接同步 Coordinator 线程和 async SSE 端点。
- **Retry / Review Policy**：节点级重试（`max_retries` 元数据）、部分结果交付（verify 失败时交付草稿报告）、人工复核队列。

**第四层：Agent 层**

四个专职 Agent，各司其职：
- **Collector**：MiMo-V2.5 + WebSearchTool，联网采集公开信息。接收 Evidence Index 预索引证据和 Memory 长期记忆。
- **Analyzer**：MiMo-V2.5，SWOT/对比结构化分析。
- **Writer**：MiMo-V2.5，生成 Markdown 报告，每条结论附 `[来源: URL]` 标注。
- **Verifier**：MiMo-V2.5-Pro（100 万 Token 上下文 + 深度推理），独立质检，不继承 Writer 历史。

**第五层：数据层**

- **SQLite 三库分治**：run_store（运行记录）、coordinator_store（DAG + Scratchpad）、source_store（来源情报）。
- **ChromaDB 向量存储**：长期记忆，存储已验证事实，支持语义检索。
- **Scratchpad**：节点间数据传递的键值存储，路径约定为 `node_key/filename.ext`。

**第六层：可观测层**

- **Prometheus**：9 个指标（run/node/llm 三层），`/metrics` 端点始终可用。
- **OTel**：分布式追踪（run.execute / node.{key} / llm.call 三级 span），支持 OTLP export。
- **SSE 事件流**：11 种事件类型覆盖完整生命周期。

**第七层：平台集成层**

- **MCP Server**：FastMCP 服务器，9 个工具，stdio + HTTP/SSE 传输。
- **复核队列**：`needs_review` 自动入队，审核 API（approve/reject/assign）。
- **企业级 Dashboard**：概览/复核/成本三个管理页面。

### 2.2 核心执行流程

完整的数据流经过以下步骤：

```
步骤 1: 用户输入
  用户通过 Web App / CLI / MCP 提交 CompetitorInput
  （productName, competitors, dimensions, analysisType）

步骤 2: Run 创建
  RunService.create_run()
  → SQLite run_store 写入 analysis_runs 记录（status=queued）
  → coordinator_store 初始化 DAG（4 个节点 + 依赖关系）
  → 写入 input/brief.json 到 Scratchpad
  → 记录 run.created 事件

步骤 3: 后台执行
  FastAPI BackgroundTasks 触发 RunService.execute_run()
  → MemoryService.query_for_run() 从 ChromaDB 检索历史事实
  → CoordinatorLoopService.execute() 启动 DAG 状态机

步骤 4: DAG 调度循环
  while True:
    检查 run 是否 cancelled
    检查是否有 failed 节点（尝试部分结果交付）
    检查是否所有节点 completed/skipped（从 Scratchpad 组装结果）
    查找 ready 节点（pending + 所有依赖 completed）
    对每个 ready 节点调用 _execute_node_with_retry()

步骤 5: 逐节点执行
  collect 节点:
    → 读取 input_data + evidence_index + memory_context
    → 创建 Crew(collector, [collect_task])
    → CrewAI kickoff → Collector 使用 WebSearchTool 搜索
    → 输出写入 Scratchpad: collect/raw.json

  analyze 节点:
    → 从 Scratchpad 读取 collect/raw.json
    → 截断到 6000 字符，注入 task description
    → 创建 Crew(analyzer, [analyze_task])
    → 输出写入 Scratchpad: analyze/findings.json

  write 节点:
    → 从 Scratchpad 读取 analyze/findings.json
    → 创建 Crew(writer, [write_task])
    → 输出写入 Scratchpad: write/report.md

  verify 节点:
    → 从 Scratchpad 读取 write/report.md
    → 创建 Crew(verifier, [verify_task])（MiMo-V2.5-Pro）
    → 输出写入 Scratchpad: verify/verifier.json

步骤 6: 结果持久化
  _persist_success():
    → 从 Scratchpad 读取报告和质检结果
    → Provenance Guard 校验（来源标注、URL、Provenance 索引）
    → 解析 Verifier JSON（passed/confidence/issues）
    → 创建 artifacts（report_markdown, verifier_json, provenance_index）
    → 提取 source_references
    → 写入 review_queue（如果 needs_review）
    → 更新 run 状态（passed / needs_review）
    → MemoryService.ingest_completed_run() 存储已验证事实

步骤 7: 事件推送
  _emit() 双写:
    → SQLite agent_events 持久化
    → EventBus.publish() → SSE 端点 → 前端实时更新
```

### 2.3 三个入口点对比

| 特性 | CLI (`main.py`) | Streamlit (`app.py`) | FastAPI (`api_app.py`) |
|------|-----------------|---------------------|----------------------|
| 适用场景 | 脚本化批量执行 | 快速原型演示 | 生产环境 |
| 用户交互 | 命令行参数 | Web 表单 | REST API + React UI |
| 执行方式 | 同步阻塞 | 同步阻塞 | 后台异步 |
| DAG 调度 | 无（直接 run_analysis） | 无（直接 run_analysis） | 有（CoordinatorLoopService） |
| 事件流 | 控制台 verbose | Streamlit 实时更新 | SSE 推送 |
| 持久化 | 无 | 无 | SQLite 三库 |
| 前端托管 | 无 | 无 | React SPA |

**关键设计决策**：`runner.py` 中的 `run_analysis()` 保持不变，作为 Phase 1 兼容路径。Phase 1.5+ 的 FastAPI 入口通过 `RunService` 包装，增加了 DAG 调度、事件持久化、Scratchpad 和 EventBus。

### 2.4 前后端交互模型

前端与后端的交互有三种模式：

**REST API**（请求-响应）：
- `POST /api/runs` — 创建分析任务
- `GET /api/runs/{run_id}` — 获取 run 详情
- `GET /api/reviews` — 获取复核列表
- `POST /api/reviews/{id}/approve` — 批准复核

**SSE 事件流**（服务器推送）：
- `GET /sse/runs/{run_id}` — 订阅 run 事件
- 前端通过 `EventSource` API 订阅
- 支持 `after_event_id` 游标实现断线重连
- 事件类型：`run.created`、`agent.started`、`agent.progress`、`agent.completed`、`verifier.issue`、`artifact.ready`、`run.completed`、`run.failed` 等 11 种

**静态文件托管**：
- FastAPI 托管 `frontend/dist/` 目录
- `/api/*` 和 `/sse/*` 路由走后端
- 其他路径回退到 `index.html`（SPA 路由）

---

## 三、Agent 编排与任务调度

### 3.1 Agent 定义模式

每个 Agent 通过 CrewAI 的 `Agent` 类定义，配置以下属性：

- **role**：Agent 的角色描述（如"竞品信息采集专家"）
- **goal**：Agent 的目标（如"采集竞品的公开信息，包含来源 URL 和原文片段"）
- **backstory**：Agent 的背景故事，用于引导 LLM 的行为模式
- **llm**：通过 `config/settings.py` 的 `create_llm()` 工厂函数创建的 LLM 实例
- **tools**：Agent 可用的工具列表（如 Collector 的 WebSearchTool）

**四个 Agent 的配置差异**：

| Agent | 模型 | 工具 | 特殊配置 |
|-------|------|------|----------|
| Collector | MiMo-V2.5 | WebSearchTool（调用 MiMo API 联网搜索） | 有工具，需要处理搜索结果 |
| Analyzer | MiMo-V2.5 | 无 | 纯文本分析，依赖上游数据 |
| Writer | MiMo-V2.5 | 无 | 格式化输出，需遵循报告规范 |
| Verifier | MiMo-V2.5-Pro | 无 | 独立模型，不继承 Writer 历史 |

**WebSearchTool 实现细节**（`crew/agents/collector.py`）：
- 通过 `litellm.completion()` 调用 MiMo API 进行联网搜索
- 返回搜索结果的摘要和 URL
- 作为 CrewAI Tool 注册到 Collector Agent

**Agent 单例模式**：每个 Agent 在模块级别创建为单例（如 `collector.py` 中的 `collector = Agent(...)`）。Phase 2 的逐节点执行器直接导入这些单例，与新创建的 Task 组合成独立的 Crew。

### 3.2 Task 链式执行

**Phase 1 的 Task 链**：

四个 Task 通过 `context=[previous_task]` 形成线性依赖链：
```
collect_info_task (context=[])
  → analyze_task (context=[collect_info_task])
    → write_task (context=[analyze_task])
      → verify_task (context=[write_task])
```

CrewAI 的 `flow="sequential"` 模式保证 Task 按顺序执行，每个 Task 的输出通过 `context` 传递给下游 Task。

**Task description 模板**：

每个 Task 的 `description` 是一个详细的提示词模板，包含：
- 执行步骤（1, 2, 3...）
- 输出格式要求（JSON Schema / Markdown 规范）
- 约束条件（如"禁止输出没有 source_references 的采集项"）

**CrewAI 模板变量**：Task description 中使用 `{productName}`、`{competitors}` 等占位符，在 `crew.kickoff(inputs=inputs)` 时由 Pydantic 模型的 `model_dump()` 填充。

**Phase 2 的 Task 解耦**：

Phase 2 的逐节点执行器不再使用 `context=[previous_task]`，而是：
1. 从 Scratchpad 读取上游输出
2. 截断到 6000 字符（`_UPSTREAM_TRUNCATE`）
3. 注入到新的 Task description 中
4. 创建独立的单节点 Crew 执行

这解耦了节点间的 Python 对象引用，支持独立重试。

### 3.3 DAG 状态机调度器

**DAG 模型**（`services/coordinator_foundation.py`）：

默认 DAG 模板定义了 4 个节点的线性链：
```python
DEFAULT_DAG_TEMPLATE = (
    {"key": "collect", "name": "Collect public evidence", "agent": "Collector", "depends_on": []},
    {"key": "analyze", "name": "Analyze competitive findings", "agent": "Analyzer", "depends_on": ["collect"]},
    {"key": "write", "name": "Write report", "agent": "Writer", "depends_on": ["analyze"]},
    {"key": "verify", "name": "Verify report quality", "agent": "Verifier", "depends_on": ["write"]},
)
```

每个 `DAGNode` 包含：
- `node_id`：UUID
- `run_id`：所属 run
- `key`：节点标识（collect/analyze/write/verify）
- `status`：节点状态（pending/running/completed/failed/skipped）
- `depends_on`：依赖的节点 key 列表
- `input_refs` / `output_refs`：Scratchpad 路径引用
- `metadata`：可扩展元数据（max_retries、retry_attempts、last_error、timeout_seconds）

**节点状态机**：
```
pending → running → completed
                  → failed → (重试) → running
                         → (后代) → skipped
```

**调度循环**（`_execute_dag()`）：
```
while True:
    1. 检查 run 是否 cancelled → 抛出 RuntimeError
    2. 获取所有节点，检查是否有 failed 节点
       → 尝试部分结果交付（verify 失败但 write 完成时返回草稿）
       → 否则抛出 RuntimeError
    3. 检查是否所有节点 completed/skipped
       → 从 context 获取 final_result（Legacy 路径）
       → 或从 Scratchpad 组装 AssembledResult（Phase 2 路径）
    4. 调用 _ready_nodes() 找到可执行节点
       → 条件：status=pending 且所有 depends_on 节点 status=completed
    5. 对每个 ready 节点调用 _execute_node_with_retry()
```

### 3.4 逐节点独立执行器

**从单体到独立的演进**：

Phase 1 的 `_legacy_chain_node_executor()` 将整条 CrewAI 链路包在 `collect` 节点中执行，其余节点被跳过。Phase 2 的 `per_node_executor()` 为每个节点创建独立的 Crew：

```python
# services/node_executors.py
def per_node_executor(*, run_id, node, context, progress_callback, foundation, **kwargs):
    executor = _NODE_EXECUTORS.get(node.key)  # collect/analyze/write/verify
    return executor(run_id=run_id, node=node, context=context, ...)
```

每个节点执行器的通用模式：
1. 从 context 读取输入数据
2. 从 Scratchpad 读取上游输出（`_read_scratchpad()`）
3. 截断到 6000 字符
4. 创建新的 Task（description 注入上游数据）
5. 创建单节点 Crew（`Crew(agents=[agent], tasks=[task], flow="sequential")`）
6. 执行 `crew.kickoff(inputs=inputs)`
7. 将输出写入 Scratchpad
8. 返回 `NodeExecutionResult`（output_refs + scratchpad_outputs）

**超时支持**：通过 `run_with_timeout()` 包裹 `executor()` 调用，超时时间从 `node.metadata["timeout_seconds"]` 读取。

**LLM 调用追踪**：通过 `trace_llm_call()` 上下文管理器包裹 `_run_single_crew()`，记录 model、node_key、prompt_length、duration。

### 3.5 节点级重试机制

**重试逻辑**（`_execute_node_with_retry()`）：

```
max_retries = node.metadata.get("max_retries", 1)  # 默认 1 次
attempts = 0
while True:
    attempts += 1
    更新 retry_attempts 元数据
    节点状态 → running
    发送 agent.started 事件
    try:
        执行 executor()
        记录 Scratchpad 输出
        更新 output_refs
        节点状态 → completed
        发送 agent.completed 事件
        return result
    except Exception:
        更新 last_error 元数据
        if attempts <= max_retries:
            发送 agent.retrying 事件
            continue
        mark_run_failed() → 节点状态 failed + 后代 skipped
        raise
```

**后代跳过**：`mark_run_failed()` 通过 BFS 遍历找到失败节点的所有后代节点，将它们标记为 `skipped`。

**节点重试 API**：`POST /api/runs/{run_id}/dag/{node_key}/retry` 调用 `reset_node_for_retry()` 将指定节点及其后代重置为 `pending`，然后重新执行 DAG。

### 3.6 Agent Harness 设计

**Coordinator 主循环模式**：

系统借鉴了 Claude Code 的 Agent Harness 设计思想：
- **主循环 + 工具调用**：Coordinator 主循环不直接执行 Agent，而是将每个 Agent 封装为"工具"（节点执行器），通过 DAG 状态机动态调度。
- **委派原则**：Coordinator 只负责任务分解和调度，不直接执行分析逻辑。
- **Scratchpad 共享目录**：节点间通过 Scratchpad 传递数据，避免上下文爆炸。

**工具化 Agent 的实现**：

每个 Agent 的执行被封装为一个独立的"工具调用"：
```python
# node_executors.py 中的 _execute_collect()
def _execute_collect(*, run_id, node, context, progress_callback, foundation):
    task = Task(description="...", agent=collector, expected_output="...")
    output = _run_single_crew(collector, task, inputs, node_key="collect")
    return NodeExecutionResult(
        output_refs=["collect/raw.json"],
        scratchpad_outputs={"collect/raw.json": output},
    )
```

**与直接调用的区别**：

| 维度 | 直接调用（Phase 1） | 工具化调用（Phase 2+） |
|------|-------------------|---------------------|
| 数据传递 | CrewAI context 链 | Scratchpad 读写 |
| 重试粒度 | 整条链路重跑 | 单节点独立重试 |
| 可观测性 | 仅控制台 verbose | 每个节点独立 span + 指标 |
| 超时控制 | 无 | 每节点可配置 timeout_seconds |
| 熔断保护 | 无 | CircuitBreaker 按 provider 管理 |

---

## 四、数据层设计

### 4.1 三库分治架构

系统使用三个独立的 SQLite 数据库，每个服务不同的关注域：

**run_store.sqlite3**（`storage/run_store.py`）：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `analysis_runs` | 分析任务记录 | run_id (PK), input_json, status, created_at, parent_run_id |
| `agent_events` | 事件日志 | event_id (AUTOINCREMENT), run_id (FK), type, agent, stage, message, payload_json |
| `artifacts` | 产物存储 | artifact_id (PK), run_id (FK), kind, content, content_preview |
| `source_references` | 来源引用 | source_id (PK), run_id (FK), uri, snippet, confidence |
| `review_queue` | 复核队列 | review_id (PK), run_id (FK), status, issues_json, assigned_to, review_notes |

**coordinator_store.sqlite3**（`storage/coordinator_store.py`）：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `dag_nodes` | DAG 节点 | node_id (PK), run_id, key, name, agent, status, depends_on_json, input_refs_json, output_refs_json, metadata_json |
| `scratchpad_items` | 中间产物 | item_id (PK), run_id, path (UNIQUE per run), kind, content, content_preview, producer_node_id |

**source_store.sqlite3**（`storage/source_store.py`）：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `source_seeds` | 来源种子 | seed_id (PK), provider, competitor, url, cadence, enabled |
| `raw_documents` | 原始文档 | document_id (PK), seed_id, content, content_hash, fetched_at |
| `evidence_items` | 证据条目 | evidence_id (PK), document_id, competitor, dimension, summary, confidence |
| `source_fetch_events` | 抓取事件 | event_id (PK), seed_id, status, error, fetched_at |

**为什么分三个库**：
1. **关注域隔离**：run_store 关注运行记录，coordinator_store 关注编排状态，source_store 关注情报数据
2. **锁竞争减少**：不同写入模式的操作不会互相阻塞
3. **独立演进**：每个库可以独立迁移（如 source_store 迁移到 PostgreSQL 而不影响其他）

**线程安全**：每个 store 使用 `threading.RLock` 保护所有数据库操作。`_connection()` 上下文管理器在每次操作时获取锁、创建连接、提交事务、关闭连接。

### 4.2 Scratchpad 中间产物系统

Scratchpad 是节点间数据传递的核心机制，替代了 CrewAI 的 `context=[previous_task]` 链。

**路径约定**：
```
input/brief.json      — 用户输入（ensure_default_dag 时写入）
collect/raw.json      — Collector 采集的原始数据
analyze/findings.json — Analyzer 的结构化分析结论
write/report.md       — Writer 生成的 Markdown 报告
verify/verifier.json  — Verifier 的质检结果 JSON
```

**数据结构**（`ScratchpadItem`）：
```python
class ScratchpadItem(BaseModel):
    item_id: str           # UUID
    run_id: str            # 所属 run
    path: str              # 键名，如 "collect/raw.json"
    kind: str              # "json" | "markdown" | "text"
    content: str           # 完整内容
    content_preview: str   # 截断到 600 字符的预览
    producer_node_id: str  # 生产该条目的节点 ID
    metadata: dict         # 扩展元数据
```

**Upsert 语义**：`write_scratchpad()` 按 `(run_id, path)` 唯一约束执行 upsert，同一路径的多次写入会覆盖。

**读取 API**：
- `get_scratchpad_item(run_id, path)` — 按路径精确读取
- `list_scratchpad_items(run_id)` — 列出某 run 的所有条目
- `CoordinatorFoundationService.list_scratchpad(run_id)` — 服务层封装

**在节点执行器中的使用**：
```python
def _execute_analyze(*, run_id, node, context, progress_callback, foundation):
    # 读取上游输出
    raw_data = _read_scratchpad(foundation, run_id, "collect/raw.json")
    truncated = _truncate(raw_data, max_chars=6000)
    # 注入到 Task description
    task = Task(description=f"读取采集数据：\n\n{truncated}\n\n执行分析...", ...)
    output = _run_single_crew(analyzer, task, {}, node_key="analyze")
    # 写入自己的输出
    return NodeExecutionResult(
        scratchpad_outputs={"analyze/findings.json": output},
    )
```

### 4.3 Protocol 存储抽象层

**设计动机**：当前所有消费端直接依赖 SQLite 具体类，PostgreSQL 迁移需要改动大量代码。Protocol 抽象层使得迁移变成"新增实现类 + 替换实例化"。

**三个 Protocol**（`storage/protocols.py`）：

```python
@runtime_checkable
class RunStoreProtocol(Protocol):
    def create_run(self, input_data, *, parent_run_id=None, status="queued") -> RunRecord: ...
    def get_run(self, run_id: str) -> RunRecord: ...
    def update_run_status(self, run_id, status, *, error=None, completed=False) -> RunRecord: ...
    def append_event(self, run_id, event_type, message, *, agent=None, stage=None, payload=None) -> AgentEvent: ...
    def list_events(self, run_id, *, after_event_id=0) -> list[AgentEvent]: ...
    def create_artifact(self, run_id, kind, content) -> ArtifactRecord: ...
    # ... 共 12 个方法

@runtime_checkable
class CoordinatorStoreProtocol(Protocol):
    def upsert_node(self, node: DAGNode) -> DAGNode: ...
    def get_node(self, run_id, key) -> DAGNode: ...
    def list_nodes(self, run_id) -> list[DAGNode]: ...
    def update_node_status(self, run_id, key, status) -> DAGNode: ...
    def write_scratchpad_item(self, item: ScratchpadItem) -> ScratchpadItem: ...
    # ... 共 9 个方法

@runtime_checkable
class SourceStoreProtocol(Protocol):
    def upsert_seed(self, seed: SourceSeed) -> SourceSeed: ...
    def query_evidence(self, *, competitor=None, dimensions=None) -> list[EvidenceItem]: ...
    # ... 共 11 个方法
```

**`@runtime_checkable` 的作用**：允许 `isinstance(store, RunStoreProtocol)` 运行时检查，测试中验证 SQLite 实现满足 Protocol。

**消费端类型标注**：
```python
# services/run_service.py
class RunService:
    def __init__(self, store: RunStoreProtocol, ...): ...

# services/coordinator_loop.py
class CoordinatorLoopService:
    def __init__(self, run_store: RunStoreProtocol, ...): ...
```

### 4.4 来源情报层

**五种 Connector**（`services/source_connectors.py`）：

| Connector | 数据源 | 获取方式 | 适用场景 |
|-----------|--------|----------|----------|
| `OfficialJinaConnector` | 官方网页 | Jina Reader API 抓取 | 产品官网、定价页 |
| `NewsApiConnector` | 新闻 | NewsAPI.org API | 行业新闻、产品发布 |
| `GitHubRepoConnector` | GitHub | GitHub REST API | 开源项目、技术文档 |
| `RssFeedConnector` | RSS/Atom | Feed 解析 | 博客、更新日志 |
| `RedditSearchConnector` | Reddit | Reddit JSON API | 用户讨论、社区反馈 |

**Evidence 提取**（`services/evidence_extractor.py`）：
- 确定性关键词匹配（非 LLM）
- 从原始文档中提取结构化证据条目（competitor, dimension, indicator, summary, source_references）
- 使用 metadata hints 指导提取方向

**Evidence 注入 Collector 提示词**：
```
Evidence Index:
- [钉钉] 定价：免费版支持最多 500 人，来源: https://dingtalk.com/pricing
- [飞书] 功能：支持文档协作和即时通讯，来源: https://feishu.cn/features
优先使用 Evidence Index 中已有的结构化证据；证据不足时再使用网络搜索补充。
```

**索引 CLI**：
```bash
python scripts/index_sources.py --init-defaults          # 初始化默认种子
python scripts/index_sources.py --index --provider official --competitor 钉钉 --limit 1
python scripts/index_sources.py --index --provider official --due-only  # 只索引到期的
```

### 4.5 长期记忆系统

**架构**：

```
Run 完成 (passed/needs_review)
  → MemoryService.ingest_completed_run(run_id)
    → 读取 report_markdown artifact
    → 验证 verifier confidence >= 70
    → 提取 claim-like 行（正则匹配 bullet points）
    → 清理来源标注和 URL
    → 确定关联的 competitor
    → VectorStore.upsert_facts() → ChromaDB 嵌入存储

新 Run 开始
  → MemoryService.query_for_run(competitors, dimensions)
    → 构造查询：每个 competitor × 每个 dimension
    → VectorStore.query_relevant() 语义搜索
    → 按 distance 排序，去重
    → format_for_prompt() 格式化为提示词文本
    → 注入 Coordinator context["memory_context"]
```

**ChromaDB 集成**（`storage/vector_store.py`）：
- 使用 `PersistentClient` 持久化到 `data/vector_store/`
- 使用 `cosine` 距离度量
- 支持 `in_memory=True` 模式（测试用，避免模型下载）
- `_SimpleEmbedding` 作为 fallback 嵌入函数（SHA-256 哈希映射到 256 维向量）

**事实提取规则**：
1. 只从 `passed` 或 `needs_review` 状态的 run 提取
2. Verifier confidence 必须 >= 70
3. 只提取 bullet point 行（`- ` 或 `* ` 开头，长度 >= 20 字符）
4. 跳过标题行和表格行
5. 清理 `[来源: URL]` 标注，保留纯文本结论
6. 从文本中识别关联的 competitor 名称

---

## 五、可靠性与韧性设计

### 5.1 CircuitBreaker 熔断器

**三态机模型**（`services/resilience.py`）：

```
closed（正常）
  → 连续失败达到 failure_threshold → open

open（熔断）
  → 拒绝所有调用，抛出 CircuitOpenError
  → 经过 cooldown_seconds → half_open

half_open（探测）
  → 允许一次调用
  → 成功 → closed
  → 失败 → open（重新开始冷却）
```

**配置参数**：
- `failure_threshold`：连续失败次数阈值（默认 5）
- `cooldown_seconds`：冷却期（默认 60 秒）
- `provider`：提供者名称（用于日志和指标）

**线程安全**：使用 `threading.Lock` 保护状态转换。

**全局注册表**（`get_circuit_breaker(provider)`）：
- 每个 provider 一个 CircuitBreaker 实例
- 通过 `get_circuit_breaker("mimo")` 获取或创建
- 确保同一 provider 共享同一个熔断器

**集成点**：
- `ModelRegistry.create_llm()` 调用前检查 `cb.check()`
- `node_executors.py` 的 `_run_single_crew()` 可选包裹 `cb.call()`

### 5.2 节点超时机制

**实现**（`run_with_timeout()`）：

```python
def run_with_timeout(fn, *args, timeout_seconds=None, **kwargs):
    if not timeout_seconds:
        return fn(*args, **kwargs)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeout:
            future.cancel()
            raise TimeoutError(f"Node execution exceeded {timeout_seconds}s timeout")
```

**配置方式**：通过 `node.metadata["timeout_seconds"]` 设置，每个节点可独立配置。

**在 coordinator_loop.py 中的集成**：
```python
timeout = node.metadata.get("timeout_seconds")
result = run_with_timeout(
    executor,
    run_id=run_id, node=node, context=context,
    timeout_seconds=float(timeout) if timeout else None,
)
```

**超时处理**：超时视为节点失败，走正常的重试流程（`_execute_node_with_retry` 的 except 分支）。

### 5.3 部分结果交付

**场景**：verify 节点失败但 write 节点已成功完成。

**当前行为**（Phase 3）：
1. `_execute_dag()` 检测到 failed 节点
2. 调用 `_try_partial_result()` 检查是否有已生成的报告
3. 如果 write 节点 status=completed 且 verify 节点 status=failed/skipped：
   - 从 Scratchpad 读取 `write/report.md`
   - 发送 `agent.progress` 事件："质检节点失败，交付草稿报告（needs_review）"
   - 返回 `AssembledResult(passed=False)`，触发 `needs_review` 状态
4. 如果没有可用的报告，抛出 RuntimeError

**与人工复核的配合**：`needs_review` 状态的 run 自动写入 `review_queue`，用户可以在 Dashboard 的复核队列中查看并决定是否接受。

### 5.4 多模型降级

**ModelRegistry**（`config/model_registry.py`）：

```python
@dataclass
class ModelProvider:
    name: str           # "mimo", "openai", "anthropic"
    base_url: str
    api_key: str
    model_name: str
    priority: int       # 1 = primary, 2 = fallback
    enabled: bool = True

class ModelRegistry:
    def register(self, role: str, provider: ModelProvider): ...
    def get_providers(self, role: str) -> list[ModelProvider]: ...  # sorted by priority
    def create_llm(self, role: str) -> LLM: ...  # try in order, skip open breakers
```

**fallback 流程**：
```
create_llm("collector"):
  providers = get_providers("collector")  # [mimo (p=1), openai (p=2)]
  for provider in providers:
    cb = get_circuit_breaker(provider.name)
    try:
      cb.check()  # raises CircuitOpenError if open
      return _create_llm_from_provider(provider)
    except CircuitOpenError:
      continue  # skip to next provider
    except Exception:
      cb.record_failure()
      continue
  raise RuntimeError("All providers failed")
```

**配置方式**：

环境变量（简单场景）：
```bash
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=sk-xxx
FALLBACK_PROVIDER=openai
FALLBACK_BASE_URL=https://api.openai.com/v1
FALLBACK_API_KEY=sk-yyy
FALLBACK_MODEL=gpt-4o-mini
```

YAML 配置（复杂场景）：
```yaml
# config/model_config.yaml
collector:
  - provider: mimo
    base_url: https://api.xiaomimimo.com/v1
    api_key: sk-xxx
    model: mimo-v2.5
    priority: 1
  - provider: openai
    base_url: https://api.openai.com/v1
    api_key: sk-yyy
    model: gpt-4o-mini
    priority: 2
verifier:
  - provider: mimo
    model: mimo-v2.5-pro
    priority: 1
```

通过 `COMPETEYE_MODEL_CONFIG` 环境变量指定 YAML 文件路径。

### 5.5 Provenance Guard 溯源守卫

**三层校验**（`services/verification.py`）：

**第一层：来源索引区块检查**
```python
if not any(marker in report for marker in SOURCE_BLOCK_MARKERS):
    issues.append("最终报告缺少 provenance / 来源索引区块")
```
检查报告是否包含 "Provenance 索引"、"provenance 索引"、"来源索引"、"参考来源" 等标记。

**第二层：URL 和来源标签检查**
```python
urls = re.findall(r"https?://[^\s\])>，。；,]+", report)
if not urls:
    issues.append("最终报告缺少可访问 URL")

source_tag_count = len(re.findall(r"\[来源:\s*[^\]]+\]", report))
claim_like_lines = _claim_like_lines(report)
if claim_like_lines and source_tag_count < len(claim_like_lines):
    issues.append(f"来源标注不足：检测到 {len(claim_like_lines)} 条结论，但只有 {source_tag_count} 个来源标注")
```

**第三层：Verifier JSON 解析**
```python
verdict = parse_verifier_result(verifier_result)
if verdict:
    if verdict.get("passed") is False:
        issues.append("Verifier 判定未通过")
    if verdict.get("confidence", 100) < 60:
        issues.append(f"置信度低于阈值: {confidence}")
    for item in verdict.get("issues", []):
        issues.append(item["description"])
```

**自动重写闭环**（`runner.py`，Phase 1 兼容路径）：
1. 首次质检失败 → 收集 issues 列表
2. 创建新的 Writer Task，description 中注入问题描述："上一次质检未通过，请修复以下问题：..."
3. 创建新的 Writer + Verifier Crew 执行
4. 二次质检失败 → 返回 issues 列表（非零退出）

### 5.6 错误处理与异常传播

**异常边界**：

| 层级 | 异常处理策略 |
|------|-------------|
| `node_executors.py` | 不捕获异常，向上传播给 coordinator_loop |
| `coordinator_loop._execute_node_with_retry()` | 捕获异常，判断是否重试，重试耗尽则 mark_run_failed + raise |
| `coordinator_loop._execute_dag()` | 捕获 failed 节点，尝试部分结果交付，否则 raise |
| `coordinator_loop.execute()` | 捕获所有异常，更新 run 状态为 failed，记录 run.failed 事件，发送 EventBus close 信号 |
| `run_service.execute_run()` | 被 coordinator_loop 内部处理，不再有额外的 try/except |
| `api_app.py` BackgroundTasks | FastAPI 框架级别的异常日志 |

**失败时的状态更新**：
```python
except Exception as exc:
    self.run_store.update_run_status(run_id, "failed", error=str(exc), completed=True)
    self._emit(run_id, "run.failed", f"Coordinator 主循环执行失败：{exc}",
               agent="Coordinator", payload={"error_type": type(exc).__name__})
finally:
    if self._event_bus is not None:
        self._event_bus.close(run_id)  # 发送 None 哨兵，关闭 SSE 流
```

---

## 六、可观测性体系

### 6.1 Prometheus 指标

**9 个指标，三层覆盖**：

| 指标 | 类型 | 维度 | 说明 |
|------|------|------|------|
| `compeye_runs_total` | Counter | status | 总 run 数（created/passed/failed/needs_review） |
| `compeye_run_duration_seconds` | Histogram | status | run 执行时长（buckets: 5/10/30/60/120/300/600s） |
| `compeye_active_runs` | Gauge | — | 当前活跃 run 数 |
| `compeye_node_duration_seconds` | Histogram | node_key | 节点执行时长（buckets: 2/5/15/30/60/120/300s） |
| `compeye_node_retries_total` | Counter | node_key | 节点重试次数 |
| `compeye_events_total` | Counter | event_type | 事件总数（按 11 种事件类型分类） |
| `compeye_llm_calls_total` | Counter | model, node_key, status | LLM 调用次数 |
| `compeye_llm_call_duration_seconds` | Histogram | model, node_key | LLM 调用延迟 |
| `compeye_llm_tokens_total` | Counter | model, node_key, direction | Token 用量（input/output） |

**`/metrics` 端点**：始终可用（无需启用 OTel），返回 Prometheus 文本格式。

**Prometheus Registry**：使用独立的 `CollectorRegistry`，避免与其他应用的指标冲突。

### 6.2 OTel 分布式追踪

**三级 Span 层次**：

```
run.execute (run_id)
  ├── node.collect (run_id, node_key, attempt)
  │     └── llm.call (model, node_key, prompt_length, duration_seconds)
  ├── node.analyze (run_id, node_key, attempt)
  │     └── llm.call (model, node_key, prompt_length, duration_seconds)
  ├── node.write (run_id, node_key, attempt)
  │     └── llm.call (model, node_key, prompt_length, duration_seconds)
  └── node.verify (run_id, node_key, attempt)
        └── llm.call (model, node_key, prompt_length, duration_seconds)
```

**OTel 初始化**（`services/telemetry.py`）：
- 默认关闭，通过 `COMPETEYE_OTEL_ENABLED=true` 启用
- TracerProvider + BatchSpanProcessor（异步批量导出）
- 支持 OTLP export（`OTEL_EXPORTER_OTLP_ENDPOINT`）或 Console 输出
- FastAPI 自动 instrumentation（`FastAPIInstrumentor.instrument_app()`）

**LLM 调用追踪**（`trace_llm_call()`）：
```python
with trace_llm_call("mimo-v2.5", "collect", prompt_length=1200) as span:
    result = crew.kickoff(inputs=inputs)
    if span:
        span.set_attribute("output_length", len(str(result)))
```

### 6.3 SSE 事件流

**11 种事件类型**：

| 事件类型 | 触发时机 | 携带数据 |
|----------|----------|----------|
| `run.created` | Run 创建时 | allow_retry |
| `run.started` | DAG 调度器启动时 | — |
| `agent.started` | 节点开始执行时 | attempt, max_retries |
| `agent.progress` | 节点执行过程中 | 阶段描述文本 |
| `agent.completed` | 节点执行成功时 | attempt |
| `agent.retrying` | 节点失败准备重试时 | attempt, max_retries, error |
| `verifier.issue` | 质检发现问题时 | 问题详情 |
| `artifact.ready` | 产物生成时 | passed, retried, source_count |
| `run.completed` | Run 正常结束时 | status |
| `run.failed` | Run 失败时 | error_type |
| `run.cancelled` | Run 被取消时 | — |

**EventBus 双写模式**：

```python
def _emit(self, run_id, event_type, message, *, agent=None, stage=None, payload=None):
    # 1. SQLite 持久化（支持断线重连）
    stored = self.run_store.append_event(run_id, event_type, message, ...)
    # 2. EventBus 内存推送（毫秒级延迟）
    if self._event_bus is not None:
        self._event_bus.publish(run_id, {
            "event_id": stored.event_id,
            "run_id": run_id, "type": event_type, ...
        })
```

**SSE 端点优先级**：
1. 优先从 EventBus 队列 await（零轮询）
2. 队列不存在时回退到 SQLite 轮询（每秒一次）
3. 收到 `None` 哨兵 → 发送 `stream.closed` → 结束

### 6.4 Run Inspector

**`GET /api/runs/{run_id}/inspector`** 返回：
```json
{
  "inspector": {
    "run_id": "...",
    "dag": {
      "node_count": 4,
      "status_counts": {"completed": 3, "failed": 1}
    },
    "scratchpad": {
      "item_count": 5,
      "paths": ["input/brief.json", "collect/raw.json", ...]
    }
  }
}
```

**Dashboard 集成**：DashboardPage 底部展示 Run Inspector 面板，显示 DAG 节点状态分布和 Scratchpad 条目列表。

### 6.5 结构化日志与审计

**当前状态**：
- 事件通过 `agent_events` 表持久化，包含完整的执行链路记录
- 每个事件有 `event_id`（自增）、`run_id`、`type`、`agent`、`stage`、`message`、`payload`
- 支持 `after_event_id` 游标分页查询

**审计能力**：
- 通过 `list_events(run_id)` 可以回溯任意 run 的完整执行历史
- `payload` 字段携带结构化数据（如 attempt 次数、错误信息、token 用量）
- Render.com 自动部署（render.yaml 配置）

---

## 十一、面试高频问题集

### 11.1 架构设计类（8 题）

**Q1: 介绍一下这个项目的整体架构？**

A: 系统采用七层架构。用户入口层提供 Web App、CLI 和 MCP Server 三种接入方式。服务层是 FastAPI Gateway，提供 REST API 和 SSE 事件流。任务编排层是核心，由 DAG 状态机调度器管理四个节点的执行，EventBus 实现毫秒级事件推送。Agent 层有四个专职 Agent：Collector（联网采集）、Analyzer（结构化分析）、Writer（报告撰写）、Verifier（独立质检）。数据层使用 SQLite 三库分治（run/coordinator/source）加 ChromaDB 向量存储。可观测层有 Prometheus 9 个指标和 OTel 分布式追踪。平台集成层包括 MCP Server、复核队列和企业级 Dashboard。

**Q2: 为什么用七层架构而不是更简单的分层？**

A: 每一层有独立的演进节奏和关注域。比如数据层从 SQLite 迁移到 PostgreSQL 只需要替换存储实现，不影响 Agent 层和编排层。可观测层从基础 Prometheus 升级到完整 OTel 也不影响业务逻辑。这种分层使得 27 个子里程碑可以逐步交付而不破坏已有功能。

**Q3: 三个入口点（CLI/Streamlit/FastAPI）是怎么共存的？**

A: 核心分析逻辑在 `runner.py` 的 `run_analysis()` 中，三个入口都调用同一个函数。CLI 和 Streamlit 直接调用 `run_analysis()`，FastAPI 通过 `RunService` 包装，增加了 DAG 调度、事件持久化和 EventBus。Phase 1 的入口保持不变作为兼容路径，Phase 1.5+ 的 FastAPI 是主要生产入口。

**Q4: 前后端是怎么交互的？**

A: 三种模式。REST API 用于请求-响应操作（创建任务、获取报告）。SSE 事件流用于实时推送（Agent 状态变化、产物生成）。静态文件托管让 FastAPI 直接服务 React SPA。SSE 端点优先从 EventBus 内存队列读取（零轮询），队列不存在时回退到 SQLite 每秒轮询。

**Q5: 系统是怎么保证水平扩展的？**

A: 当前是单进程部署，但架构已为扩展做好准备。存储层通过 Protocol 抽象，SQLite 可替换为 PostgreSQL。EventBus 用 asyncio.Queue，可替换为 Redis Pub/Sub 支持多进程。BackgroundTasks 可替换为 Celery/RQ 任务队列。这些改动互不影响。

**Q6: 系统的核心数据流是什么？**

A: 用户输入 → CompetitorInput 验证 → RunService 创建 run → CoordinatorLoopService 启动 DAG 状态机 → 逐节点执行（collect→analyze→write→verify）→ 每个节点从 Scratchpad 读上游输出、写自己的输出 → Provenance Guard 校验 → 持久化产物 → EventBus 推送事件 → 前端实时更新。

**Q7: 如果要支持 100 并发用户，需要改什么？**

A: 四个改动。1) SQLite → PostgreSQL（Protocol 接口已就绪）。2) asyncio.Queue → Redis Pub/Sub。3) BackgroundTasks → Celery 任务队列。4) 添加连接池（asyncpg）和缓存层（Redis）。存储抽象层的设计使得这些改动可以逐个进行。

**Q8: 系统的单点故障在哪里？怎么缓解？**

A: SQLite 是单点故障（单文件）。缓解措施：Protocol 抽象层使得 PostgreSQL 迁移只需新增实现类。LLM API 是另一个单点：CircuitBreaker + 多模型降级可以自动 fallback 到备用提供者。

### 11.2 Agent 编排类（8 题）

**Q9: 四个 Agent 分别做什么？为什么这样分工？**

A: Collector 负责联网采集公开信息（使用 WebSearchTool），Analyzer 执行 SWOT/对比结构化分析，Writer 生成 Markdown 报告，Verifier 独立质检。分工原则是单一职责：每个 Agent 只做一件事，输入输出结构清晰。Verifier 特别使用 MiMo-V2.5-Pro（100 万 Token 上下文），不继承 Writer 历史，强制独立判断，防确认偏误。

**Q10: Agent 之间的数据是怎么传递的？**

A: Phase 1 使用 CrewAI 的 `context=[previous_task]` 链式传递，这是内存中的 Python 对象引用。Phase 2 升级为 Scratchpad（SQLite-backed 键值存储），每个节点读取上游的 Scratchpad 产物、写入自己的输出。路径约定如 `collect/raw.json`、`write/report.md`。这解耦了节点间依赖，支持独立重试。

**Q11: DAG 调度器是怎么工作的？**

A: 调度器是一个 while True 循环。每轮：1) 检查 run 是否 cancelled。2) 检查是否有 failed 节点（尝试部分结果交付）。3) 检查是否所有节点 completed（从 Scratchpad 组装结果）。4) 调用 `_ready_nodes()` 找到可执行节点（pending + 所有依赖 completed）。5) 对每个 ready 节点调用 `_execute_node_with_retry()`。

**Q12: 节点级重试是怎么实现的？**

A: `_execute_node_with_retry()` 读取 `node.metadata["max_retries"]`（默认 1），循环执行。每次失败时更新 `retry_attempts` 和 `last_error` 元数据，发送 `agent.retrying` 事件。重试耗尽时调用 `mark_run_failed()` 将节点标记为 failed、后代标记为 skipped，然后抛出异常。

**Q13: 逐节点执行器和 Phase 1 的单体链路有什么区别？**

A: Phase 1 的 `_legacy_chain_node_executor()` 将整条 CrewAI 链路包在 `collect` 节点中执行，其余节点被跳过。Phase 2 的 `per_node_executor()` 为每个节点创建独立的 Crew，从 Scratchpad 读取上游数据，独立执行。区别在于：数据传递从 context 链变为 Scratchpad 读写，重试粒度从整条链路变为单节点，可观测性从控制台 verbose 变为每个节点独立 span。

**Q14: 为什么不用 Celery 或 Airflow 做任务编排？**

A: 当前的 DAG 是 4 节点线性链，复杂度不高，自研的 `_execute_dag()` 只有 ~50 行代码，足够清晰。引入 Celery/Airflow 会增加运维复杂度和外部依赖。但架构已通过 Protocol 和 EventBus 为未来的替换做好了准备。

**Q15: Agent 的 Prompt 是怎么管理的？**

A: 每个 Task 的 `description` 是一个详细的提示词模板，定义在 `tasks/` 目录下。模板包含执行步骤、输出格式要求、约束条件。CrewAI 的模板变量（`{productName}` 等）在 `kickoff(inputs=inputs)` 时填充。Phase 2 的逐节点执行器还会在 description 中注入上游 Scratchpad 内容（截断到 6000 字符）。

**Q16: 如果 Collector 采集的信息质量很差，系统怎么处理？**

A: 三层保障。1) Evidence Index 预索引：来源情报层提前从 5 种 Connector 采集结构化证据，注入 Collector 提示词作为参考。2) Provenance Guard：报告必须有来源标注和 URL，缺失则判失败。3) Verifier 独立质检：MiMo-V2.5-Pro 检查逻辑矛盾、幻觉、缺失证据，confidence < 60 触发重写。

### 11.3 数据与存储类（6 题）

**Q17: 为什么用三个 SQLite 数据库？**

A: 关注域分离。run_store 管运行记录和事件（高频写入），coordinator_store 管 DAG 和 Scratchpad（编排状态），source_store 管来源情报（独立刷新周期）。三个库避免不同写入模式的锁竞争。每个库使用 threading.RLock 保证线程安全。

**Q18: Scratchpad 是什么？和 CrewAI context 有什么区别？**

A: Scratchpad 是 SQLite-backed 的键值存储，路径约定为 `node_key/filename.ext`。和 CrewAI context 的区别：1) context 是内存中的 Python 对象引用，节点间耦合强；Scratchpad 是持久化的，支持断点续跑。2) context 链无法独立重试单个节点；Scratchpad 支持。3) Scratchpad 内容可通过 Run Inspector API 查询。

**Q19: Protocol 抽象层是怎么设计的？**

A: 使用 Python 的 `typing.Protocol`（`@runtime_checkable`），定义三个接口：RunStoreProtocol（12 个方法）、CoordinatorStoreProtocol（9 个方法）、SourceStoreProtocol（11 个方法）。SQLite 实现通过鸭子类型满足 Protocol，不需要显式继承。测试中使用 `isinstance(store, RunStoreProtocol)` 验证一致性。PostgreSQL 迁移只需新增实现类。

**Q20: 来源情报层是怎么工作的？**

A: 5 种 Connector（Jina/NewsAPI/GitHub/RSS/Reddit）定期抓取公开数据，存入 source_store 的 raw_documents 表。Evidence Extractor 使用关键词匹配（非 LLM）从原始文档中提取结构化证据。运行时，Evidence Service 查询匹配的证据，格式化后注入 Collector 的提示词。这减少了 Collector 对实时网络搜索的依赖。

**Q21: 长期记忆系统是怎么设计的？**

A: 使用 ChromaDB 向量存储。Run 完成后自动提取报告中的 claim-like 行，过滤 confidence >= 70 的已验证事实，嵌入存储。新 run 开始时，MemoryService 按 competitor × dimension 构造查询，语义搜索相关历史事实，格式化为提示词注入 Collector/Analyzer。使用 SimpleEmbedding 作为 fallback（SHA-256 哈希），生产环境可换 sentence-transformers。

**Q22: 数据库迁移策略是什么？**

A: 三步走。1) Protocol 抽象层已完成（storage/protocols.py）。2) 新增 PgRunStore 等实现类，使用 psycopg 连接池和 JSONB 列。3) 用 Alembic 管理 schema 版本。SQLite 实现保留作为开发/测试环境。消费端代码零改动。

### 11.4 可靠性与韧性类（6 题）

**Q23: CircuitBreaker 的三态机是怎么工作的？**

A: closed（正常）→ 连续失败达阈值 → open（熔断，拒绝调用）→ 冷却期结束 → half_open（探测，允许一次调用）→ 成功则 closed，失败则重新 open。阈值和冷却期可配置。线程安全，使用 threading.Lock。

**Q24: 多模型降级是怎么实现的？**

A: ModelRegistry 按 agent role 注册多个 provider，每个有优先级。`create_llm()` 按优先级尝试，通过 CircuitBreaker 检查健康状态，熔断的 provider 自动跳过。支持环境变量（MIMO + FALLBACK_*）和 YAML 两种配置方式。

**Q25: 部分结果交付是什么意思？**

A: 当 verify 节点失败但 write 节点已成功时，系统返回草稿报告（needs_review 状态）而非完全失败。`_try_partial_result()` 检查 write 节点是否 completed，如果是则从 Scratchpad 读取报告返回。配合人工复核队列，用户可以决定是否接受草稿。

**Q26: 节点超时是怎么实现的？**

A: 通过 `run_with_timeout()` 函数，使用 `ThreadPoolExecutor` + `future.result(timeout=...)` 实现。超时时间从 `node.metadata["timeout_seconds"]` 读取，每个节点可独立配置。超时视为节点失败，走正常重试流程。

**Q27: Provenance Guard 检查什么？**

A: 三层校验。1) Regex 检查报告必须有来源索引区块（"Provenance 索引"等标记）。2) 来源标签数必须匹配结论数（`[来源: URL]` 的数量 >= bullet point 结论的数量）。3) Verifier JSON 解析（passed/confidence/issues）。失败时自动重跑 Writer+Verifier 一次。

**Q28: 错误是怎么从节点传播到 run 的？**

A: 节点执行器不捕获异常 → coordinator_loop 的 `_execute_node_with_retry()` 捕获，判断是否重试 → 重试耗尽则 `mark_run_failed()`（节点 failed + 后代 skipped）+ raise → `_execute_dag()` 捕获，尝试部分结果交付 → `execute()` 捕获，更新 run 状态为 failed，记录 run.failed 事件，发送 EventBus close 信号。

### 11.5 可观测性类（5 题）

**Q29: 系统有哪些 Prometheus 指标？**

A: 9 个指标分三层。Run 层：runs_total（按状态）、run_duration_seconds、active_runs。Node 层：node_duration_seconds（按 node_key）、node_retries_total。LLM 层：llm_calls_total（按 model/node_key/status）、llm_call_duration_seconds、llm_tokens_total（按 direction）。`/metrics` 端点始终可用。

**Q30: OTel 追踪的 Span 层次是什么？**

A: 三级。`run.execute`（run_id）→ `node.{collect|analyze|write|verify}`（run_id, node_key, attempt）→ `llm.call`（model, node_key, prompt_length, duration_seconds）。默认关闭，通过 `COMPETEYE_OTEL_ENABLED=true` 启用。

**Q31: SSE 事件流的 11 种事件类型分别是什么？**

A: run.created、run.started、agent.started、agent.progress、agent.completed、agent.retrying、verifier.issue、artifact.ready、run.completed、run.failed、run.cancelled。覆盖了从任务创建到结束的完整生命周期。

**Q32: EventBus 的双写模式是什么？**

A: `_emit()` 先 SQLite 持久化（支持断线重连），再 EventBus 内存队列推送（毫秒级延迟）。SSE 端点优先 await 事件队列，队列不存在时回退到 SQLite 轮询。通过 `loop.call_soon_threadsafe()` 桥接同步 Coordinator 线程和 async SSE 端点。

**Q33: Run Inspector 提供什么信息？**

A: `GET /api/runs/{run_id}/inspector` 返回 DAG 节点状态分布（completed/failed/pending 各几个）和 Scratchpad 条目列表（路径和预览）。Dashboard 底部展示 Inspector 面板。

### 11.6 Agent Harness 专项（8 题）

**Q34: 什么是 Agent Harness？你的系统怎么实现的？**

A: Agent Harness 是 Agent 的运行时环境，负责调度、监控、错误处理和资源管理。本系统的 Coordinator 主循环就是 Agent Harness：它通过 DAG 状态机调度四个节点执行器，每个执行器创建独立的 CrewAI Crew 运行一个 Agent。Harness 不直接执行分析逻辑，只负责任务分解和调度（委派原则）。

**Q35: Coordinator 和 Agent 的关系是什么？**

A: Coordinator 是调度器，Agent 是执行者。Coordinator 通过 DAG 状态机决定哪个 Agent 该执行，通过节点执行器创建 Crew 并调用 `kickoff()`。Agent 的输入来自 Scratchpad（由 Coordinator 传递），输出写回 Scratchpad（由 Coordinator 持久化）。Coordinator 还负责错误处理、重试、事件记录和结果组装。

**Q36: 工具化 Agent 是什么意思？**

A: 将每个 Agent 的执行封装为一个"工具调用"。节点执行器就是一个工具：接收输入（Scratchpad 内容 + context），调用 CrewAI Crew 执行，返回输出（Scratchpad 产物）。这使得 Agent 的执行可以被监控、重试、超时控制，而不是一个黑盒的 `kickoff()` 调用。

**Q37: Agent 之间的上下文是怎么管理的？**

A: 三层上下文。1) Run 级别：CompetitorInput、evidence_index、memory_context，存在 DAG context dict 中。2) 节点级别：上游 Scratchpad 内容，截断到 6000 字符注入 Task description。3) Agent 级别：每个 Agent 的 role/goal/backstory，定义在 `crew/agents/` 中。

**Q38: 怎么防止 Agent 的输出质量退化？**

A: 四层保障。1) Task description 中的格式约束（如"禁止输出没有 source_references 的采集项"）。2) Provenance Guard 规则校验。3) Verifier 独立质检（不同模型、不继承历史）。4) 人工复核队列（needs_review 状态自动入队）。

**Q39: Agent 的执行超时怎么处理？**

A: 通过 `run_with_timeout()` 包裹，超时时间从 `node.metadata["timeout_seconds"]` 读取。超时视为节点失败，走 `_execute_node_with_retry()` 的重试流程。重试耗尽则后代节点标记为 skipped。

**Q40: 怎么调试 Agent 的行为？**

A: 三种方式。1) OTel 追踪：每个 Agent 的执行有独立的 span，记录输入大小、输出大小、耗时。2) Scratchpad：每个阶段的中间产物持久化，可通过 API 查询。3) SSE 事件流：实时查看 Agent 的状态变化和进度消息。

**Q41: 如果要增加一个新的 Agent（比如翻译 Agent），需要改什么？**

A: 四步。1) 在 `crew/agents/` 定义新 Agent。2) 在 `tasks/` 定义新 Task。3) 在 `services/coordinator_foundation.py` 的 `DEFAULT_DAG_TEMPLATE` 添加节点和依赖。4) 在 `services/node_executors.py` 添加执行器函数并注册到 `_NODE_EXECUTORS`。无需改动调度器核心逻辑。

### 11.7 记忆系统专项（5 题）

**Q42: 系统有哪些层次的记忆？**

A: 三层。1) 短期记忆：Scratchpad（每个 run 的中间产物，SQLite-backed）。2) 工作记忆：DAG context dict（run 级别的输入数据和配置）。3) 长期记忆：ChromaDB 向量存储（跨 run 的已验证事实，语义检索）。

**Q43: 长期记忆的写入时机和写入内容是什么？**

A: Run 完成后（passed 或 needs_review），`MemoryService.ingest_completed_run()` 自动提取。写入内容是报告中的 claim-like 行（bullet points），过滤条件是 Verifier confidence >= 70。每条事实包含文本、关联的 competitor、来源 URL 和 run_id。

**Q44: 长期记忆的读取时机和使用方式是什么？**

A: 新 run 开始时，`RunService._execute_with_coordinator()` 调用 `MemoryService.query_for_run(competitors, dimensions)` 检索相关历史事实。结果格式化为提示词文本，注入 Coordinator 的 `memory_context`，传递给节点执行器。Collector 和 Analyzer 可以参考历史事实避免重复采集。

**Q45: ChromaDB 的嵌入函数用的是什么？**

A: 当前使用 `_SimpleEmbedding`（SHA-256 哈希映射到 256 维向量）作为 fallback，适用于离线环境和 CI。生产环境应替换为 sentence-transformers 的 all-MiniLM-L6-v2 模型，ChromaDB 会自动检测并使用。

**Q46: 记忆系统的局限性是什么？**

A: 三个局限。1) 事实提取依赖正则匹配，可能遗漏非 bullet point 格式的结论。2) SimpleEmbedding 的语义相似度质量有限，生产环境需要真正的嵌入模型。3) 没有记忆衰减机制，旧事实可能与新事实冲突。

### 11.8 工具执行专项（5 题）

**Q47: Collector 的 WebSearchTool 是怎么实现的？**

A: 通过 `litellm.completion()` 调用 MiMo API 进行联网搜索。作为 CrewAI Tool 注册到 Collector Agent。Tool 的 `run()` 方法接受搜索查询，返回搜索结果的摘要和 URL。

**Q48: 来源情报层的 5 种 Connector 分别做什么？**

A: OfficialJinaConnector 通过 Jina Reader API 抓取官方网页。NewsApiConnector 通过 NewsAPI.org 获取新闻。GitHubRepoConnector 通过 GitHub REST API 获取开源项目信息。RssFeedConnector 解析 RSS/Atom feed。RedditSearchConnector 通过 Reddit JSON API 搜索社区讨论。

**Q49: Evidence 提取是 LLM 驱动的吗？**

A: 不是。`evidence_extractor.py` 使用确定性关键词匹配，从原始文档中提取结构化证据条目。使用 metadata hints（competitor 名称、dimension 关键词）指导提取方向。这比 LLM 提取更快、更可预测、成本更低。

**Q50: 工具执行的错误怎么处理？**

A: 节点执行器不捕获 CrewAI 的异常，向上传播给 coordinator_loop。CircuitBreaker 记录失败，达到阈值后熔断。超时通过 ThreadPoolExecutor 实现。重试由 `_execute_node_with_retry()` 管理，重试耗尽则后代跳过。

**Q51: 怎么添加新的数据源 Connector？**

A: 实现 `SourceConnector` Protocol 的 `fetch()` 方法，返回 `RawDocument`。在 `source_connectors.py` 的 `connector_for_provider()` 中注册。在 `config/source_seeds.py` 中添加默认种子配置。

### 11.9 错误处理专项（5 题）

**Q52: 系统的异常分层是什么？**

A: 四层。节点执行器层（不捕获，向上传播）→ coordinator_loop 层（捕获，判断重试/部分结果/失败）→ run_service 层（由 coordinator 内部处理）→ api_app 层（FastAPI 框架级异常日志）。每层只处理自己能处理的异常。

**Q53: 节点失败后后代节点怎么处理？**

A: `mark_run_failed()` 通过 BFS 遍历找到失败节点的所有后代节点，将它们标记为 `skipped`。这避免了无意义的执行（如 analyze 失败后不需要执行 write 和 verify）。

**Q54: 部分结果交付的触发条件是什么？**

A: `_try_partial_result()` 检查：1) write 节点 status=completed。2) verify 节点 status=failed 或 skipped。3) Scratchpad 中有 `write/report.md`。三个条件都满足时返回草稿报告（needs_review）。

**Q55: EventBus 在异常时怎么处理？**

A: `execute()` 的 `finally` 块中调用 `event_bus.close(run_id)`，发送 `None` 哨兵关闭 SSE 流。即使 run 异常失败，前端也能收到 `stream.closed` 事件并更新状态。

**Q56: 怎么保证事件不丢失？**

A: 双写模式。SQLite 持久化保证事件不丢（即使 EventBus 队列被丢弃）。SSE 端点支持 `after_event_id` 游标，断线重连时从上次位置继续读取。

### 11.10 权限沙箱专项（4 题）

**Q57: 当前的权限模型是什么？**

A: 零认证，CORS 全开放。所有端点公开可访问。这是 Phase 1/2 的设计选择——优先验证核心功能，权限留到 Phase 3。

**Q58: 如果要加 RBAC，需要改什么？**

A: 五步。1) 添加 User 模型（user_id, role, team_id）。2) 添加 JWT/OAuth2 认证中间件。3) 在 `analysis_runs` 表添加 `created_by` 字段。4) 每个端点添加权限检查装饰器。5) Run 查询按 team 过滤。Protocol 抽象层使得这些改动不影响存储层。

**Q59: Agent 级权限是什么？**

A: 设计文档定义了 `AgentPermissions`（read_only, allow_network, allow_write_final_report）。当前通过 Prompt 约束实现（如 Collector 的 "禁止输出没有 source_references 的采集项"），未来可在工具调用层强制校验。

**Q60: 怎么防止 Agent 访问不该访问的数据？**

A: 当前没有沙箱。每个 Agent 可以访问整个 Scratchpad。未来可以通过 `node.metadata["allowed_scratchpad_paths"]` 限制每个节点只能读取指定路径的 Scratchpad 内容。

### 11.11 MCP 与平台集成类（4 题）

**Q61: MCP Server 是什么？你实现了哪些工具？**

A: MCP (Model Context Protocol) 是 Anthropic 定义的 Agent 互操作协议。我用 FastMCP 实现了 9 个工具：create_run、get_run、get_report、get_verification、list_runs、get_sources、get_scratchpad、cancel_run。支持 stdio（Claude Desktop）和 HTTP/SSE（远程）两种传输。

**Q62: create_run 为什么是异步执行的？**

A: MCP 工具是同步函数，不能阻塞等待分钟级的分析完成。所以在工具函数内部启动 daemon thread 执行分析，立即返回 run_id。调用者通过 get_run 轮询状态。

**Q63: MCP 工具和 REST API 有什么区别？**

A: 功能上等价，都调用同一个 RunService。区别在于协议：REST API 是 HTTP 请求-响应，MCP 是 stdio/HTTP 的工具调用协议。MCP 面向 Agent 工作台（Claude Code），REST 面向 Web 前端。

**Q64: 未来的平台集成路线是什么？**

A: 三个方向。1) 飞书/钉钉机器人：Webhook 接入，支持发起任务、接收报告。2) Webhook 通知：run 完成时推送外部通知。3) 企业知识库：接入内部知识库作为额外来源。

### 11.12 工程实践类（5 题）

**Q65: 测试策略是什么？**

A: 145 个测试分三层。单元测试（pytest）覆盖每个 service/store 模块，使用 tempfile 隔离 SQLite，使用 @patch 隔离全局状态。组件测试（vitest）覆盖前端工具函数。E2E 验证（手动）已完成一次 Phase 1.5 真实验证。

**Q66: 怎么保证测试隔离？**

A: SQLite 用 tempfile.TemporaryDirectory 创建独立数据库。ChromaDB 用 in_memory=True + 唯一 collection name。MCP 测试用 @patch.object 替换全局 store。CrewAI 用 mock 返回预定义结果。

**Q67: 代码风格和协作规范是什么？**

A: AGENTS.md 定义了 Karpathy 编码规范：Think Before Coding、Simplicity First、Surgical Changes、Goal-Driven Execution、Verification Honesty。修改前先读相关模块，保持现有命名风格，优先小改动。

**Q68: CI/CD 流程是什么？**

A: GitHub 推送 → GitHub Actions 运行 pytest + npm test → Docker 多阶段构建（Node 22 构建前端 + Python 3.12 运行后端）→ Render.com 自动部署。

**Q69: 怎么管理配置？**

A: 三层。1) `.env` 文件（本地开发，不提交）。2) `.env.example`（模板）。3) 环境变量（生产部署）。`config/settings.py` 在 import 时加载 .env、清理代理变量、配置 UTF-8。模型配置支持环境变量和 YAML 两种方式。

### 11.13 系统设计扩展类（4 题）

**Q70: 如果要支持并行 DAG 执行（如同时采集多个竞品），需要改什么？**

A: 当前 `_execute_dag()` 已经对所有 ready 节点循环执行，但用的是同步 for 循环。改为并行只需用 `concurrent.futures.ThreadPoolExecutor` 包裹 ready 节点的执行。DAG 模型和依赖推进逻辑不需要改动。

**Q71: 如果要支持语义 Diff（对比两次 run 的报告差异），怎么设计？**

A: 需要 NLP 相似度计算。可以：1) 将两次报告按段落分割。2) 用嵌入模型计算段落级相似度。3) 标记新增/删除/修改的段落。4) 在 ReportPage 展示 diff 视图。

**Q72: 如果要接入飞书机器人，架构上需要改什么？**

A: 新增 `services/feishu_adapter.py`，实现飞书消息格式适配和 Webhook 接收。复用 RunService 的 create_run/retry_run/ approve_review 方法。事件通过 EventBus 订阅，格式化为飞书消息卡片推送。不需要改动核心架构。

**Q73: 系统的设计哲学是什么？**

A: 三个核心原则。1) 可编排：把竞品分析抽象为 DAG 工作流，而非硬编码的脚本。2) 可追踪：每个 Agent 的状态、产物、质检结果都可以被追踪。3) 可校验：报告结论必须有来源标注，缺失则触发重写或标记待核实。参考了 Claude Code 的主循环、Scratchpad、独立 Verification Agent 等工程思想。

**Q74: 如果从零开始重新设计，会做什么不同的选择？**

A: 三个改进。1) 从一开始就用 PostgreSQL + Protocol 抽象，避免后续迁移成本。2) 从一开始就用 DAG 而非 CrewAI sequential chain，减少 Phase 2 的重构量。3) 从一开始就设计 MCP Server 接口，让系统天然支持 Agent 互操作。

---

## 十二、技术决策记录

### 12.1 为什么用 CrewAI 而非自研 Agent 框架？

**决策**：Phase 1 使用 CrewAI，Phase 2 通过 DAG 调度器 + 逐节点执行器逐步解耦。

**理由**：CrewAI 提供了 Agent 定义、Task 链式执行、context 传递等开箱即用的能力，加速了 MVP 验证。Phase 2 的逐节点执行器使每个节点的 Crew 是独立创建的，不再是模块级单例，为未来替换为自研运行时做好了准备。

**权衡**：CrewAI 的 sequential 模式限制了并行执行能力，但当前 4 节点线性链不需要并行。

### 12.2 为什么 SQLite 三库分治？

**决策**：三个独立的 SQLite 数据库（run_store、coordinator_store、source_store）。

**理由**：关注域分离减少锁竞争。run_store 是高频写入（事件日志），coordinator_store 是编排状态（DAG 节点），source_store 是情报数据（独立刷新周期）。单文件部署零运维。

**权衡**：SQLite 不支持多进程并发写入，但当前单进程部署足够。Protocol 抽象层使得 PostgreSQL 迁移只需新增实现类。

### 12.3 为什么 EventBus 用 asyncio.Queue？

**决策**：基于 `asyncio.Queue` 的内存事件队列，通过 `loop.call_soon_threadsafe()` 桥接同步线程。

**理由**：单进程部署下 asyncio.Queue 延迟最低、无外部依赖。双写模式（SQLite + Queue）保证了持久化和实时性的平衡。

**权衡**：不支持多进程。多进程部署时可替换为 Redis Pub/Sub，接口不变。

### 12.4 为什么 Verifier 用不同模型？

**决策**：Verifier 使用 MiMo-V2.5-Pro（100 万 Token 上下文 + 深度推理），其他 Agent 使用 MiMo-V2.5。

**理由**：质检需要更强的推理能力和更大的上下文窗口（需要读取完整报告 + 原始数据）。独立模型实例不继承 Writer 历史，强制独立判断，防确认偏误。这是参考了 Claude Code 的 Verification Agent 模式。

**权衡**：MiMo-V2.5-Pro 成本更高，但只用于质检环节，总体成本可控。

### 12.5 为什么 Scratchpad 用 SQLite 而非文件系统？

**决策**：Scratchpad 存储在 coordinator_store.sqlite3 的 scratchpad_items 表中。

**理由**：SQLite 支持事务、并发安全、结构化查询。文件系统需要手动管理文件锁和清理。SQLite 的 upsert 语义天然支持同一路径的多次写入。

**权衡**：大文件（如长报告）在 SQLite 中存储效率不如文件系统，但当前报告大小在可接受范围内。

### 12.6 为什么 Protocol 而非 ABC？

**决策**：使用 `typing.Protocol`（`@runtime_checkable`）而非 `abc.ABC`。

**理由**：Protocol 是结构性子类型（鸭子类型），SQLite 实现不需要显式继承 Protocol，保持了代码的简洁性。`@runtime_checkable` 允许 `isinstance()` 检查用于测试验证。

**权衡**：Protocol 不支持默认方法实现，但当前不需要。

### 12.7 为什么 ChromaDB 而非自建向量索引？

**决策**：使用 ChromaDB 作为向量存储后端。

**理由**：ChromaDB 提供了开箱即用的持久化向量存储、嵌入函数管理、语义搜索 API。自建向量索引需要处理嵌入模型加载、索引构建、持久化等复杂问题。

**权衡**：ChromaDB 的首次使用需要下载 ONNX 嵌入模型（79MB），我们在测试中使用 SimpleEmbedding 作为 fallback。

---

## 十三、未来优化方向

| 方向 | 说明 | 预估工作量 | 优先级 |
|------|------|-----------|--------|
| **PostgreSQL 迁移** | Protocol 接口已就绪，需新增 PgRunStore 等实现类 + Alembic 迁移脚本 | 中 | 高 |
| **RBAC 权限系统** | 用户模型 + JWT 认证 + 权限中间件 + Team 隔离 | 大 | 高 |
| **飞书/钉钉接入** | 协作平台机器人，Webhook 接入，消息卡片格式适配 | 中 | 中 |
| **Webhook 通知** | run 完成/复核时推送外部通知（Slack、飞书、邮件） | 小 | 中 |
| **并行 DAG 执行** | ThreadPoolExecutor 包裹 ready 节点执行 | 小 | 中 |
| **Grafana Dashboard** | OTel 数据已就绪，需配置 Grafana + OTLP Collector | 小 | 低 |
| **Semantic Diff** | 对比两次 run 的报告差异，需要 NLP 相似度计算 | 中 | 低 |
| **真正的嵌入模型** | 替换 SimpleEmbedding 为 sentence-transformers | 小 | 中 |
| **记忆衰减机制** | 旧事实降权，避免与新事实冲突 | 小 | 低 |

---

*本报告由 CompEyeAgent 项目自动生成，覆盖全部 27 个子里程碑的技术细节和 74 道面试参考问题。*

---

## 七、人工复核与权限

### 7.1 复核队列

**数据模型**（`ReviewItem`）：
```python
class ReviewItem(BaseModel):
    review_id: str
    run_id: str
    status: ReviewStatus  # "pending" | "in_review" | "approved" | "rejected"
    issues: list[str]     # 质检发现的问题列表
    assigned_to: str | None
    review_notes: str | None
    created_at: str
    updated_at: str
    reviewed_at: str | None
```

**自动入队逻辑**：当 `_persist_success()` 判定 `result.passed == False` 时，自动调用 `store.create_review(run_id, issues)` 写入 `review_queue` 表。

**审核 API**：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/reviews` | GET | 列出复核项，支持 `status` 和 `run_id` 过滤 |
| `/api/reviews/{id}` | GET | 获取单个复核详情 |
| `/api/reviews/{id}/approve` | POST | 批准，可附带 `notes` |
| `/api/reviews/{id}/reject` | POST | 驳回，可附带 `notes` |
| `/api/reviews/{id}/assign` | POST | 指派审核人 |

### 7.2 审核工作流

```
needs_review 状态的 run
  → 自动写入 review_queue (status=pending)
  → Dashboard 复核页面展示
  → 审核人操作：
     → approve: status → approved, reviewed_at = now()
     → reject:  status → rejected, reviewed_at = now()
     → assign:  assigned_to = "张三", status → in_review
```

### 7.3 权限沙箱设计

**当前状态**：零认证，CORS 全开放。所有端点公开可访问。

**Protocol 预留**：存储层已通过 Protocol 抽象，`created_by` 字段可在不改动消费端的情况下添加到 `analysis_runs` 表。

**RBAC 路线图**（未来优化方向）：
1. User 模型（user_id, username, email, role, team_id）
2. JWT/OAuth2 认证中间件
3. 权限检查装饰器（谁可以创建 run、谁可以查看报告、谁可以审批）
4. Team/workspace 隔离（run 查询按 team 过滤）

### 7.4 Agent 级权限

设计文档（DESIGN.md Optimization 12）定义了 Agent 级权限模型：
```python
class AgentPermissions(BaseModel):
    read_only: bool = False           # 只读模式，不允许写入最终报告
    allow_network: bool = False       # 是否允许联网搜索
    allow_write_final_report: bool = False  # 是否允许写入最终报告
```

当前通过 Prompt 约束实现（如 Collector 的 "禁止输出没有 source_references 的采集项"），未来可在工具调用层强制校验。

---

## 八、前端工程

### 8.1 技术选型

| 技术 | 版本 | 选型理由 |
|------|------|----------|
| React | 19.2.3 | 组件化、生态成熟 |
| TypeScript | 5.9.3 | 类型安全，减少运行时错误 |
| Vite | 7.2.7 | 快速 HMR、原生 ESM |
| React Router | 7.11.0 | SPA 路由，支持嵌套布局 |
| Vitest | 4.0.16 | 与 Vite 深度集成的测试框架 |
| 纯 CSS | — | 800 行设计系统，CSS 自定义属性，无框架依赖 |

**无 CSS 框架的考量**：项目 UI 相对简单（数据展示为主），不需要 Tailwind 或 Ant Design 的全部能力。手写 CSS 通过 CSS 自定义属性（`--bg-elevated`、`--accent`、`--border` 等）实现主题一致性，响应式断点在 1080px 和 720px。

### 8.2 页面架构

| 页面 | 路径 | 功能 |
|------|------|------|
| OverviewPage | `/overview` | 统计卡片（总数/通过/复核/失败）、最近任务列表、待审核快捷入口 |
| DemoPage | `/demo` | 对话式任务创建、快速示例填充、Brief 表单编辑 |
| DashboardPage | `/dashboard/:runId` | 实时执行追踪（SSE 事件流）、Agent 阶段卡片、Artifact 摘要、Run Inspector |
| ReportPage | `/reports/:runId` | Markdown 报告渲染、下载按钮（MD/JSON）、Verifier 结果、来源卡片 |
| ReviewPage | `/reviews` | 复核队列列表、状态过滤、approve/reject/assign 操作 |
| CostPage | `/costs` | Token 使用量汇总、按 run 明细表 |

### 8.3 SSE 实时订阅

**DashboardPage 的 SSE 订阅逻辑**：

```typescript
const source = openRunEventStream(runId);
setStreamStatus("connected");

// 订阅所有事件类型
STREAM_EVENTS.forEach((eventName) => source.addEventListener(eventName, handleEvent));

// 处理 stream 结束
source.addEventListener("stream.closed", (message) => {
    setStreamStatus("closed");
    const data = JSON.parse(message.data);
    setRun(prev => prev ? { ...prev, status: data.status } : prev);
    loadRun(); loadInspector(); // 刷新数据
    source.close();
});

source.onerror = () => setStreamStatus("reconnecting");
```

**事件合并**：`mergeEvents()` 函数按 `event_id` 去重并排序，确保重连时不丢失事件。

**状态派生**：`deriveStageStates()` 从事件历史中推导每个 Agent 阶段的状态（done/active/waiting），用于 Dashboard 的阶段卡片展示。

### 8.4 API 客户端设计

**类型安全的 fetch 封装**（`frontend/src/api/client.ts`）：

```typescript
async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json", ...init?.headers },
        ...init,
    });
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    return response.json() as Promise<T>;
}
```

**端点映射**：每个后端 API 端点对应一个 TypeScript 函数，返回类型与 Pydantic 模型镜像（`frontend/src/api/types.ts`）。

---

## 九、平台集成

### 9.1 MCP Server

**MCP（Model Context Protocol）** 是 Anthropic 定义的 Agent 互操作协议，允许 Claude Code、Codex 等 Agent 工作台调用外部工具。

**实现**（`mcp_server.py`）：
- 使用 `mcp.server.fastmcp.FastMCP` 创建服务器
- 通过 `@mcp.tool` 装饰器注册工具函数
- 支持 stdio 传输（Claude Desktop 直接调用）和 HTTP/SSE 传输（远程访问）

**9 个 MCP 工具**：

| 工具 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `create_run` | product_name, competitors, dimensions, analysis_type | run_id, status | 发起分析，后台异步执行 |
| `get_run` | run_id | status, events, product | 查询任务状态 |
| `get_report` | run_id | report (Markdown) | 获取分析报告 |
| `get_verification` | run_id | passed, confidence, issues | 获取质检结果 |
| `list_runs` | limit | runs 列表 | 列出最近任务 |
| `get_sources` | run_id | sources 列表 | 获取来源引用 |
| `get_scratchpad` | run_id | items 列表 | 获取中间产物 |
| `cancel_run` | run_id | status | 取消运行中的任务 |

### 9.2 MCP 工具设计模式

**异步执行**：`create_run` 在工具函数内部启动 daemon thread 执行分析，立即返回 run_id。这是因为 MCP 工具是同步函数，不能阻塞等待分钟级的分析完成。

**状态查询**：`get_run` 返回最新状态和最近 5 个事件，调用者可以轮询直到状态变为 terminal。

**Claude Desktop 配置**：
```json
{
  "mcpServers": {
    "compeye": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": { "MIMO_BASE_URL": "...", "MIMO_API_KEY": "..." }
    }
  }
}
```

### 9.3 未来集成路线

| 方向 | 说明 | 预估工作量 |
|------|------|-----------|
| 飞书/钉钉机器人 | 协作平台 Webhook 接入，支持发起任务、接收报告 | 中 |
| Webhook 通知 | run 完成/复核时推送外部通知 | 小 |
| 企业知识库 | 接入企业内部知识库作为额外来源 | 中 |

---

## 十、测试与质量保障

### 10.1 测试分层策略

| 层级 | 工具 | 数量 | 覆盖范围 |
|------|------|------|----------|
| 单元测试 | pytest | 135 | 每个 service/store 模块独立可测 |
| 组件测试 | vitest | 10 | 前端工具函数 |
| E2E 验证 | 手动 | 1 | Phase 1.5 已完成一次真实 E2E 验证 |

### 10.2 测试隔离技术

**SQLite 隔离**：每个测试使用 `tempfile.TemporaryDirectory()` 创建独立的数据库文件，tearDown 时清理。

**ChromaDB 隔离**：使用 `VectorStore(in_memory=True, collection_name=f"test_{uuid.uuid4().hex[:8]}")` 创建独立的内存实例，避免共享状态。

**MCP Server 隔离**：使用 `@patch.object(mcp_server, "store", self._store)` 替换全局 store 引用，tearDown 恢复原始值。

**CrewAI 隔离**：测试中 mock `crew.kickoff()` 返回预定义结果，不实际调用 LLM API。

### 10.3 145 个测试的分布

| 测试文件 | 数量 | 覆盖模块 |
|----------|------|----------|
| test_coordinator_foundation.py | 14 | DAG 创建、Scratchpad、API 端点、节点调度、重试、取消 |
| test_verification.py | 12 | Provenance Guard、Verifier 解析、来源标签检查 |
| test_resilience.py | 15 | CircuitBreaker 状态机、超时、全局注册表 |
| test_model_registry.py | 8 | 注册表 CRUD、环境变量构建、YAML 构建 |
| test_telemetry.py | 14 | Prometheus 指标记录、OTel span、LLM 指标 |
| test_event_bus.py | 7 | EventBus create/publish/close/discard |
| test_store_protocols.py | 4 | Protocol 一致性验证 |
| test_memory_service.py | 12 | ChromaDB CRUD、事实提取、语义查询 |
| test_mcp_server.py | 10 | 所有 MCP 工具函数 |
| test_source_layer.py | ~15 | 来源存储、Connector、Evidence 提取 |
| test_source_refresh.py | ~3 | 刷新频率逻辑 |
| test_source_seed_registry.py | ~3 | 默认种子注册 |
| test_collect_task_prompt.py | ~1 | 提示词模板验证 |
| test_static_frontend.py | 3 | FastAPI 静态文件托管 |
| test_run_service.py | ~2 | 取消 run 等 |
| frontend runData.test.ts | 3 | buildCreateRunRequest、deriveStageStates、selectArtifacts |

### 10.4 CI/CD 流程

- 代码推送到 GitHub main 分支
- GitHub Actions 运行 `python -m pytest`（后端）和 `npm test`（前端）
- Docker 多阶段构建：Node 22 构建前端 → Python 3.12 运行后端
- Render.com 自动部署（render.yaml 配置）





