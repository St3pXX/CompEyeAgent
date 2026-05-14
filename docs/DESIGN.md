# 竞品分析 Agent 协作系统 — 完整架构设计文档 (V2.0)

**版本**：2.0
**最后更新**：2026-05-13
**设计状态**：完整蓝图（Phase 1 MVP 已实现部分功能，Phase 2/3 规划优化）
**文档用途**：GitHub 仓库设计说明书，展示系统完整性与工程深度

---

## 1. 系统概述

### 1.1 业务目标
解决传统竞品分析流程繁琐重复、信息源分散、依赖个人经验的痛点。构建一个由多专职 Agent 协作的自动化系统，完成从公开信息采集到结构化竞品报告的全链路工作，并确保**每条结论可溯源、每个决策可观测**。

### 1.2 核心能力矩阵

| 能力 | 说明 | 课题对应 |
|------|------|----------|
| **多角色协作** | 采集、分析、撰写、质检四个专职 Agent 协同 | 模拟真实调研小组 |
| **任务编排** | 基于主控循环 + 工具化 Agent，支持动态 DAG | DAG 式任务流转 |
| **交叉审查闭环** | 独立质检 Agent + 规则引擎，防确认偏误 | 交叉审查反馈闭环 |
| **结果溯源** | 工具层强制约束，每条结论附来源 URL + 原文片段 | 有据可查 |
| **可观测性** | 三层模型：产品事件 + OTel 指标 + 会话语义追踪 | 决策过程透明 |
| **韧性设计** | 重试/降级/人工兜底，部分可用策略 | 系统稳定性 |

---

## 2. 设计哲学：借鉴 Claude Code 源码思想

本系统深度借鉴 Claude Code（51.2 万行 TypeScript 工程）的多项核心设计原则，并非简单使用 Agent 框架，而是将工业级工程思想注入竞品分析场景。

| Claude Code 思想 | 本系统落地位置 | 实现阶段 |
|----------------|---------------|----------|
| **主循环 + 工具调用**（单线程主循环，Agent 通过工具完成工作） | Coordinator 主循环，采集/分析/撰写/质检封装为工具 | Phase 2 |
| **Scratchpad 共享目录**（跨 Agent 数据旁路传递，避免上下文爆炸） | 文件系统 Scratchpad，采集结果 JSON 供分析直接读取 | Phase 2 |
| **独立 Verification Agent**（全新进程，不继承历史，防确认偏误） | 质检 Agent 使用不同模型实例，仅接收报告+证据 | Phase 1 已实现 |
| **工具层强制溯源**（工具 API 要求返回 sources，否则报错） | Phase 1 先通过 Prompt + 规则层 provenance guard 约束输出；Phase 2 升级为工具 API 层强制校验与自动重试 | Phase 1 雏形 / Phase 2 强化 |
| **可观测性分层**（产品事件 + OTel 指标 + 会话语义追踪） | 三层模型：业务事件 / 技术指标 / 决策链路 | Phase 2 |
| **流式 Generator 透出**（实时输出内部活动，支持中断） | `async generator` + SSE 推送 Agent 状态 | Phase 2 |
| **Coordinator 委派原则**（主控不直接执行，只分解任务和调度） | 设计上强调委派优先，实现上允许 Coordinator 调用部分工具 | 设计文档约束 |

---

## 3. 系统架构图（V2.0）

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                            用户 / UI                                     │
│                    (CLI / Streamlit / 未来 API)                          │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ (流式事件 SSE)
┌─────────────────────────────────▼───────────────────────────────────────┐
│                        Coordinator (主控 Agent)                          │
│  - 主循环 while(tool_calls)                                              │
│  - 任务分解与 DAG 生成                                                    │
│  - 子 Agent 调度 (通过工具调用)                                           │
│  - 状态持久化 (短期记忆)                                                  │
└───────────────┬─────────────┬─────────────┬─────────────┬───────────────┘
                │             │             │             │
      ┌─────────▼──────┐ ┌────▼─────────┐ ┌─▼──────────┐ ┌▼───────────┐
      │ 采集工具       │ │ 分析工具     │ │ 撰写工具   │ │ 质检工具   │
      │ (Collect)      │ │ (Analyze)    │ │ (Compose)  │ │ (Verify)   │
      │ 调用 MiMo-V2.5 │ │ 调用 MiMo-V2.5│ │ MiMo-V2.5 │ │ MiMo-Pro   │
      └─────────┬──────┘ └────┬─────────┘ └─┬──────────┘ └┬───────────┘
                │             │             │             │
                └─────────────┴─────────────┴─────────────┘
                                  │
                ┌─────────────────▼─────────────────────────────────┐
                │            Scratchpad (共享文件系统)               │
                │  - raw/     采集原始数据 (JSON + 元数据)           │
                │  - parsed/  清洗后结构化数据                       │
                │  - analysis/分析结论 (含 provenance)              │
                │  - drafts/  报告草稿                              │
                │  - tasks/   任务状态 (DAG 节点文件)               │
                │  - provenance/溯源映射索引                        │
                └─────────────────┬─────────────────────────────────┘
                                  │
                ┌─────────────────▼─────────────────────────────────┐
                │         可观测性三层模型                           │
                │  L1: 产品事件 (用户行为日志)                        │
                │  L2: OTel 指标 (调用链、延迟、Token)               │
                │  L3: 会话语义追踪 (SemanticStep 序列)              │
                └────────────────────────────────────────────────────┘
```

---

## 4. 核心数据模型

### 4.1 竞品知识 Schema（用户输入）

```json
{
  "productName": "产品名称",
  "competitors": ["竞品A", "竞品B"],
  "dimensions": [
    {"name": "定价", "indicators": ["免费版", "付费版", "API 价格"]},
    {"name": "功能", "indicators": ["协作", "集成"]}
  ],
  "analysisType": "SWOT"
}
```

### 4.2 Provenance（溯源对象）— 完整版

```python
from typing import List, Optional
import uuid
from enum import Enum

class ConfidenceLevel(str, Enum):
    HIGH = "high"       # 0.9～1.0  直接源, 高信度
    MEDIUM = "medium"   # 0.6～0.89 二次源, 部分推理
    LOW = "low"         # 0.0～0.59 弱证据, 需人工复核

class SourceRef(BaseModel):
    uri: str                    # 文件路径或 URL
    snippet: str                # 关键原文片段
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    fetch_time: str             # ISO 时间戳

class Provenance(BaseModel):
    conclusion_id: str = str(uuid.uuid4())
    text: str
    source_references: List[SourceRef] = []
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    generated_by: str           # "collector" | "analyzer" | "writer" | "verifier"
    parent_trace_id: str        # 会话语义追踪 ID
```

### 4.3 任务状态文件（DAG 节点持久化）

```json
{
  "task_id": "collect_price_A",
  "type": "collect",
  "status": "succeeded",
  "input": {"competitor": "产品A", "dimension": "定价"},
  "output_ref": "scratchpad/raw/collect_price_A.json",
  "depends_on": [],
  "blocked_by": [],
  "retry_count": 0,
  "error": null,
  "created_at": "2026-05-13T10:00:00Z"
}
```

### 4.4 会话语义追踪（SemanticStep）

```json
{
  "step_id": "step_001",
  "session_trace_id": "sess_abc123",
  "parent_step_id": null,
  "agent_type": "coordinator",
  "action": "decide_next_task",
  "input_summary": "用户需求: 分析产品A vs 产品B 定价",
  "output": "生成任务: collect_price_A, collect_price_B",
  "evidence_links": ["scratchpad/provenance/sess_abc123/step_001_prov.json"],
  "timestamp": "2026-05-13T10:00:01Z"
}
```

---

## 5. 优化点详细设计

本章逐个阐述 12 项核心优化的设计原理、工程实现及在 Phase 1/2/3 的落地计划。

### 优化 1：主 Agent 循环 + 工具化专职 Agent

**原理**
不预设静态 DAG，而是由一个主循环（Coordinator）动态调用工具化的专职 Agent。每个专职 Agent 被封装为一个 **Tool**（如 `collect_tool`, `analyze_tool`），由 Coordinator 根据上下文决定调用顺序和策略。

**工程实现**
```python
# 伪代码
tools = [CollectTool(), AnalyzeTool(), ComposeTool(), VerifyTool()]
while True:
    response = llm.invoke(messages, tools=tools)
    if not response.tool_calls:
        break
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call)
        messages.append({"role": "tool", "content": result})
```

**Phase 落地**
- Phase 1：使用 CrewAI 顺序执行（简化版，替代静态 DAG）
- Phase 2：重写为自研主循环 + 工具化 Agent，支持动态决策
- Phase 3：支持并行工具调用 + 子 Agent 派生

---

### 优化 2：独立 Verification Agent（不继承历史）

**原理**
质检 Agent 必须是一个 **全新进程/调用**，不继承撰写 Agent 的任何对话历史。只接收三部分：原始需求、报告草稿、所有溯源记录。系统提示强调"主动找问题，而非确认正确性"。

**工程实现**
- 使用不同模型实例（MiMo-V2.5-Pro）
- 在调用前清空 messages，只注入专门的质检 prompt
- 输出结构包含 `passed`, `confidence`, `issues` 数组

**Phase 落地**
- Phase 1：已实现（Verifier Agent 独立，不同模型）
- Phase 2：增加历史对比功能，检测报告版本间差异

---

### 优化 3：质检双层结构（规则引擎 + 模型辅助）

**原理**
第一层：确定性规则（必填字段、来源 URL 格式、章节完整性），用代码实现，速度快、无幻觉。
第二层：大模型进行语义校验（逻辑矛盾、数据不一致、幻觉检测），输出置信度。

**工程实现**
```python
def verify_report(report, context):
    # 规则层
    if not has_required_sections(report):
        return {"passed": False, "reason": "missing_sections"}
    if not all_conclusions_have_provenance(report):
        return {"passed": False, "reason": "missing_provenance"}
    # 模型层
    model_verdict = llm_check(report, context)
    return model_verdict
```

**Phase 落地**
- Phase 1：仅模型层（简化）
- Phase 2：增加规则引擎，两层并行
- Phase 3：支持用户自定义规则（DSL）

---

### 优化 4：可观测性三层模型

**原理**
- **L1 产品事件层**：记录用户操作（分析开始、报告导出、人工干预），用于业务分析。
- **L2 OTel 指标层**：标准 OpenTelemetry 指标（延迟、Token 消耗、调用次数）、链路追踪、结构化日志。
- **L3 会话语义追踪层**：记录每个 Agent 的决策步骤（SemanticStep），形成完整推理链，支持 UI 下钻。

**工程实现**
- L1：结构化 JSON 写入本地文件或 ClickHouse
- L2：集成 OpenTelemetry SDK，暴露 metrics/traces
- L3：每个 Agent 调用前后生成 SemanticStep 对象，存入内存/文件，关联 `session_trace_id`

**Phase 落地**
- Phase 1：控制台日志 + 基础 provenance（L3 雏形）
- Phase 2：集成 OpenTelemetry + 产品事件记录
- Phase 3：可视化 Dashboard（Grafana + 自定义 UI）

---

### 优化 5：智能重试与人工兜底

**原理**
根据质检 Agent 输出的问题类型，触发不同修正策略：
- 缺失证据 → 调用采集工具补充特定字段
- 逻辑矛盾 → 调用分析工具重新分析，附带矛盾证据
- 多次失败后转入人工队列（邮件 / 看板）

**工程实现**
```python
if verification.passed:
    return report
else:
    for issue in verification.issues:
        if issue.type == "missing_evidence":
            retry_collect(issue.field)
        elif issue.type == "logical_conflict":
            retry_analyze(issue.context)
    retry_count += 1
    if retry_count >= MAX_RETRY:
        send_to_human_queue(report, verification)
```

**Phase 落地**
- Phase 1：最多 1 次重试，无人工队列
- Phase 2：支持 3 次重试 + 人工兜底（简单邮件通知）
- Phase 3：集成工单系统 / Slack 通知

---

### 优化 6：Scratchpad 共享目录

**原理**
采集 Agent 将原始数据写入文件系统的共享目录（如 `scratchpad/raw/`），分析 Agent 直接从该目录读取，避免通过主控 Agent 传递大量数据，防止上下文爆炸。

**工程实现**
- 目录结构（见架构图）
- 每个写入文件返回 URI（如 `file://scratchpad/raw/collect_001.json`）
- 分析 Agent 通过 Read 工具读取文件内容

**Phase 落地**
- Phase 1：内存 dict 替代（简化）
- Phase 2：实现文件系统 Scratchpad + URI 引用
- Phase 3：支持对象存储（MinIO/S3）

---

### 优化 7：工具层强制溯源约束

**原理**
在工具 API 层面要求模型输出必须包含 `source_references` 字段。如果模型未提供，工具返回错误（BlockingError），逼迫模型重试或补充。

**工程实现**
```python
def collect_tool(url: str) -> dict:
    content = fetch(url)
    # 强制要求模型在响应中包含 sources
    response = llm.invoke("请提取信息并附上来源", tools=...)
    if "source_references" not in response or not response["source_references"]:
        raise BlockingError("Missing source_references. Please include provenance.")
    return response
```

**Phase 落地**
- Phase 1：Prompt 层面强制要求 + runner 规则层 provenance guard，未加溯源则质检判为不通过
- Phase 2：工具 API 层面强制校验 + 自动重试
- Phase 3：增加区块链式不可变溯源存证（可选）

---

### 优化 8：Generator 流式透出

**原理**
使用 Python `async generator` 逐步 yield Agent 的内部活动（任务开始/结束、中间输出、日志），前端通过 SSE 实时接收并展示，用户可在早期发现方向错误时中断。

**工程实现**
```python
async def run_analysis_stream(user_input):
    yield {"type": "status", "message": "启动协调器..."}
    async for step in coordinator.run(user_input):
        yield step
        if step["type"] == "task_error" and user_wants_abort():
            break
```

**Phase 落地**
- Phase 1：控制台实时打印（`print` 代替 `yield`）
- Phase 2：实现真正的 `async generator` + SSE 端点
- Phase 3：支持 WebSocket 双向通信

---

### 优化 9：Coordinator 委派原则（拥有工具但原则委派）

**原理**
设计文档中明确：Coordinator 原则上不直接执行具体任务，而是将工作委派给专职 Agent（工具）。但为了方便实现，Coordinator 可以保留调用部分工具的能力（如读 Scratchpad），在设计上强调"委派优先"。

**工程实现**
- 代码注释：`# Coordinator 原则上只调度，不执行具体分析`
- 工具调用规则：只有 `collect/analyze/compose/verify` 四类核心工具由 Agent 执行，Coordinator 可用辅助工具（如 `read_scratchpad`）

**Phase 落地**
- Phase 1：CrewAI 无明确 Coordinator
- Phase 2：自研 Coordinator 时遵守此原则
- Phase 3：使用权限系统强制执行（见优化 12）

---

### 优化 10：Plan Mode 可选开关

**原理**
在生成最终报告前，强制系统先输出一个"分析大纲 + 数据论点映射表"，经用户（或高级质检 Agent）审批后再进入撰写阶段，避免方向性错误导致返工。

**工程实现**
```python
if plan_mode_enabled:
    plan = coordinator.create_plan(user_input)
    if user_approves(plan):
        execute_plan(plan)
    else:
        user_modify_plan()
```

**Phase 落地**
- Phase 1：未实现
- Phase 2：作为可选特性，通过环境变量启用
- Phase 3：集成到 UI 中（开关 + 可视化计划编辑）

---

### 优化 11：持久化记忆（短期任务记忆 + 长期企业知识库）

**原理**
- **短期记忆**：当前分析会话的任务状态、中间结论、已采集 URL，用于断点恢复（会话恢复）。
- **长期记忆**：历史分析报告、已验证的事实（价格、功能）、用户偏好，存入向量库 + 图数据库，供后续分析参考。

**工程实现**
- 短期：SQLite / Redis，按 `session_id` 存储状态
- 长期：ChromaDB（向量） + NetworkX（图），定期从 Scratchpad 提取更新

**Phase 落地**
- Phase 1：无持久化
- Phase 2：短期记忆（文件存储任务状态）
- Phase 3：长期记忆 + 相关性检索

---

### 优化 12：权限表设计（简化布尔标志）

**原理**
为每个 Agent 分配最小权限：哪些工具可调用、哪些目录可读写。简化版用布尔标志（如 `read_only`, `allow_network`）。

**工程实现**
```python
class AgentPermissions(BaseModel):
    read_only: bool = False          # 只能读 Scratchpad
    allow_network: bool = False      # 可发起 HTTP 请求
    allow_write_final_report: bool = False  # 可写入最终报告

permissions = {
    "collector": AgentPermissions(read_only=False, allow_network=True),
    "analyzer": AgentPermissions(read_only=True, allow_network=False),
    "writer": AgentPermissions(read_only=False, allow_network=False, allow_write_final_report=True),
    "verifier": AgentPermissions(read_only=True, allow_network=False),
}
```

**Phase 落地**
- Phase 1：无显式权限控制
- Phase 2：在工具调用前检查权限，抛出异常
- Phase 3：集成更细粒度的 RBAC

---

## 6. 分阶段实施路线图

| 阶段 | 时间 | 范围 | 已包含优化 |
|------|------|------|------------|
| **Phase 1 (MVP)** | 已完成 | 四 Agent 顺序链路，CLI + Streamlit，控制台可观测，基础 provenance | 优化2（独立 Verifier 雏形）、优化3（模型层质检）、优化5（简化重试） |
| **Phase 2 (增强)** | 1-2 个月 | 自研 Coordinator 主循环，Scratchpad 文件系统，流式 SSE，工具层强制溯源，短期记忆 | 优化1、6、7、8、9、10、12 部分 |
| **Phase 3 (企业级)** | 3-6 个月 | 长期记忆库，语义 Diff，韧性设计（熔断/降级/人工兜底），权限系统，完整 OTel | 优化4（完整）、优化5（人工兜底）、优化11 |

---

## 7. 技术选型与部署

| 组件 | Phase 1 选型 | Phase 2/3 升级方向 |
|------|-------------|-------------------|
| 多 Agent 框架 | CrewAI | 自研主循环 + 工具化 |
| 模型 API | MiMo-V2.5 / Pro | 支持多模型 fallback |
| 存储 | 内存 dict | 文件系统 (scratchpad) → MinIO |
| 状态管理 | 无 | SQLite → Redis |
| 可观测性 | 控制台日志 | OpenTelemetry + ClickHouse + Grafana |
| 流式传输 | 无 | SSE → WebSocket |
| 记忆库 | 无 | ChromaDB + NetworkX |

**部署建议**
- 开发测试：Docker Compose（Python + Redis + MinIO）
- 生产环境：K8s + 对象存储 + Prometheus stack

---

## 8. 总结

本设计文档（V2.0）为竞品分析 Agent 协作系统提供了完整的架构蓝图，涵盖从基础链路到企业级优化的全貌。通过借鉴 Claude Code 的核心工程思想，系统不仅实现了自动化分析闭环，更在**可观测性、溯源强制性、韧性设计**上达到了工业级标准。Phase 1 MVP 已跑通并开源，后续阶段将按路线图逐步实现各项高级优化。
