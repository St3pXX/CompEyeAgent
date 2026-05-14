# CompEye Agent — AI 竞品分析 Agent 协作系统

> 多 Agent 协同，自动完成竞品信息采集 → 分析 → 报告生成，每条结论可溯源。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 产品介绍

CompEye Agent 是面向产品、市场、战略和研发团队的竞品分析工作台。系统将公开资料采集、结构化分析、报告撰写和独立质检拆分为多个专职 Agent，通过统一的任务编排和证据模型，完成从需求输入到可信报告交付的完整流程。

与传统“人工搜索 + 手工整理”的竞品调研方式不同，CompEye Agent 强调三点：

- **分析过程自动化**：把目标产品、竞品、分析维度和重点指标转化为可执行任务链路。
- **结论可追溯**：报告中的关键判断需要关联来源 URL、原文片段和 provenance 索引。
- **执行过程可观测**：每个 Agent 的状态、产物、质检结果和重试动作可以被追踪、复盘和治理。

产品最终形态不是单一网页工具，而是一个可被 Web、CLI、MCP Server、飞书、钉钉等入口调用的竞品分析基础能力。

---

## 🏗️ 最终目标架构

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                  Product Site / Full-screen Demo / Dashboard / API           │
│             对话式输入 · 实时进度 · Run Inspector · 报告/证据导出           │
└──────────────────────────────────────┬─────────────────────────────────────┘
                                       │  FastAPI + SSE / async events
┌──────────────────────────────────────▼─────────────────────────────────────┐
│                              Coordinator 主循环                             │
│  - 将需求拆成 competitor × dimension × indicator 的 DAG 节点               │
│  - 调度 Collector / Analyzer / Writer / Verifier 工具化 Agent              │
│  - 根据 Verifier issue 类型决定补采、重析、重写或人工复核                  │
└───────────────┬────────────────┬────────────────┬────────────────┬────────┘
                │                │                │                │
        ┌───────▼───────┐ ┌──────▼──────┐ ┌───────▼──────┐ ┌───────▼───────┐
        │ Collector      │ │ Analyzer    │ │ Writer       │ │ Verifier       │
        │ 公开信息采集   │ │ 结构化分析  │ │ 报告撰写     │ │ 独立交叉审查   │
        │ Evidence JSON  │ │ Claim/Finding│ │ Markdown     │ │ Issue JSON      │
        └───────┬───────┘ └──────┬──────┘ └───────┬──────┘ └───────┬───────┘
                │                │                │                │
┌───────────────▼────────────────▼────────────────▼────────────────▼────────┐
│                         Scratchpad + Run Store                              │
│ raw/ 原始采集 · evidence/ 证据 · claims/ 论点 · drafts/ 草稿 ·              │
│ verification/ 质检结果 · tasks/ DAG 状态 · provenance/ 溯源索引 · events   │
└──────────────────────────────────────┬─────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼─────────────────────────────────────┐
│                             Observability                                   │
│ 产品事件 · Token/延迟指标 · SemanticStep 决策链 · 每条结论可追溯证据       │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 工程设计原则

系统不是把多个 Agent 串联起来生成一份报告，而是把竞品分析抽象为可编排、可追踪、可校验的工作流。设计上参考了 Claude Code 在主循环、工具调用、上下文管理和可观测性上的工程思路，并将其转化到竞品分析场景中：

| 工程原则 | 本系统如何落地 |
|----------------|---------------|
| **主循环 + 工具调用** | Coordinator 主循环动态调度四类工具，Agent 不直接执行，只通过工具协作 |
| **Scratchpad 共享目录** | Phase 2 将实现文件系统 Scratchpad，采集数据旁路传递，避免上下文爆炸 |
| **独立 Verification Agent** | 质检 Agent 使用 MiMo-V2.5-Pro，**不继承撰写者历史**，独立判断，防确认偏误 |
| **规则层溯源校验** | `runner.py` 会检查最终报告是否包含来源标注 / URL / provenance，缺失则判失败 |
| **流式 Generator 透出** | Phase 1 使用 `verbose=True` 控制台实时打印，Phase 1.5 先通过 FastAPI SSE 暴露运行事件 |
| **分层可观测性** | 控制台日志（L3 语义追踪雏形）+ OTel 指标（Phase 2） |

核心目标是让每个 Agent 职责单一、输入输出结构清晰，并且让系统能够解释“为什么得出这个结论、由谁生成、依据来自哪里、是否经过质检”。

---

## ✅ 当前 Phase 1 已实现

```text
Streamlit / CLI
      │
      ▼
CrewAI 顺序链路
Collector → Analyzer → Writer → Verifier
      │
      ▼
Markdown 报告 + Provenance 索引 + Verifier JSON
      │
      ▼
runner.py 规则层 provenance guard + 最小重写闭环
```

Phase 1 的定位是验证核心闭环：四类专职 Agent 能协作完成竞品资料采集、分析、撰写和独立质检，并通过规则层 guard 保证报告至少具备逐条来源标注、可访问 URL 和 provenance 索引。

## 🤖 模型分工（MiMo 系列）

| Agent | 模型 | 职责 | 为什么用它 |
|-------|------|------|-----------|
| **Collector** | MiMo-V2.5 | 联网搜索采集公开信息 | 性价比高，联网搜索能力强 |
| **Analyzer** | MiMo-V2.5 | SWOT / 对比结构化分析 | 日常分析任务，V2.5 足够 |
| **Writer** | MiMo-V2.5 | 生成 Markdown 报告 | 格式化输出，V2.5 足够 |
| **Verifier** | MiMo-V2.5-Pro | **独立校验**（逻辑矛盾/幻觉/缺失证据） | 100万 Token 上下文 + 复杂推理，Pro 专属 |

> MiMo-V2.5-Pro 仅用于需要深度逻辑校验的质检环节，实现"让专业的做专业的事"。

---

## 🚀 在线体验

👉 **在线 Demo：** [https://compeyeagent.streamlit.app/](https://compeyeagent.streamlit.app/)

当前网页端已经提供产品化输入，不需要手写 JSON：

- 输入目标产品和竞品名称
- 勾选分析维度，填写重点指标
- 点击示例按钮一键填充演示案例
- 点击开始分析后，可看到 Collector / Analyzer / Writer / Verifier 的阶段进度
- 默认启用快速演示模式，只跑一次完整质检以缩短等待时间；关闭后会启用“失败自动重写一次”的严格复检链路

后续产品形态会从 Streamlit MVP 升级为：

- **产品介绍页**：说明系统定位、核心能力、可观测性与溯源设计
- **全屏对话体验**：独立前端页面，用户像发起对话一样提交竞品分析需求
- **实时 Dashboard**：通过 SSE 展示 Collector / Analyzer / Writer / Verifier 的协作过程、事件日志、产物状态和质检结果
- **真实后端交互**：FastAPI 提供任务创建、结果查询、SSE 事件流和报告/证据产物接口
- **云端可访问部署**：用户可直接打开网页体验，无需本地运行
- **MCP 与协作平台接入**：作为 MCP Server 接入 Claude Code、Codex 等 Agent 工作台，并接入飞书、钉钉等企业协作平台

---

## 📊 阶段进展

### 总体阶段

| 阶段 | 状态 | 核心目标 | 主要交付 |
|------|------|----------|----------|
| **Phase 1: 可运行 MVP** | ✅ 已完成 | 跑通真实多 Agent 竞品分析链路 | Streamlit 在线入口、CLI、CrewAI 顺序链路、MiMo 原生搜索、Verifier 质检、最小重写闭环、规则层 provenance guard |
| **Phase 1.5: 在线产品 Demo** | 🔨 规划中 | 把当前可运行链路包装成可持续迭代的在线产品形态 | FastAPI 包装层、React 全屏对话页、Dashboard、Report 页、SSE 事件流、SQLite/JSON run store、云端部署；前端按最终信息架构设计，预留 DAG / Scratchpad / Run Inspector 数据接口 |
| **Phase 2: 任务编排增强** | 📋 规划中 | 在不重做前端页面的前提下，增强后端任务编排和可观测数据源 | 自研 Coordinator、DAG 拆解、Scratchpad、Run Inspector 数据接口、工具层 provenance、短期任务记忆 |
| **Phase 3A: 企业级运行底座** | 📋 规划中 | 提升稳定性、治理能力和可维护性 | PostgreSQL/Redis、长期记忆库、完整 OTel 指标、权限系统、多模型 fallback、人工复核队列 |
| **Phase 3B: 平台化集成** | 📋 规划中 | 将竞品分析能力接入外部工作流和 Agent 生态 | MCP Server、Claude Code / Codex 接入、飞书/钉钉机器人、Webhook、企业知识库集成 |


**产品体验**

- Phase 1 当前状态：Streamlit 表单化输入、阶段进度、报告预览。
- Phase 1.5 规划：全屏对话式任务发起、报告详情页、运行历史、Dashboard 时间线；交互模型按长期产品形态设计。
- Phase 2 规划：接入 DAG 节点、Scratchpad 产物、Run Inspector 下钻、任务恢复、人工复核入口。
- Phase 3A 规划：团队空间、权限视图、企业级审计。
- Phase 3B 规划：外部平台内发起任务、接收报告、处理复核通知。

**前端页面**

- Phase 1 当前状态：`app.py` 单体 Streamlit 页面。
- Phase 1.5 规划：React/Vite 一次性搭建产品介绍页、Demo 页、Dashboard、Report 页，并预留 DAG / evidence / inspector 数据结构。
- Phase 2 规划：不重做页面，补齐真实数据绑定、错误态、空态、长任务状态和下钻视图。
- Phase 3A 规划：管理后台、权限配置、运行监控页。
- Phase 3B 规划：MCP 文档页、飞书/钉钉集成配置页。

**后端架构**

- Phase 1 当前状态：`runner.py` + CrewAI 顺序执行。
- Phase 1.5 规划：FastAPI 提供 `/api/runs`、`/api/runs/{id}`、`/sse/runs/{id}`、`/api/artifacts/{id}`，先包装现有真实链路。
- Phase 2 规划：Coordinator 主循环、工具化 Agent、DAG 状态机、Run Inspector API。
- Phase 3A 规划：多租户任务调度、企业级权限、审计、限流。
- Phase 3B 规划：MCP Server、飞书/钉钉机器人服务、Webhook 分发。

**数据与存储**

- Phase 1 当前状态：内存结果 + Markdown 输出。
- Phase 1.5 规划：Run Store 使用 SQLite/JSON 保存 run、event、artifact、source reference 元数据。
- Phase 2 规划：Scratchpad 保存 Agent 中间产物、DAG 节点状态和 provenance 细节。
- Phase 3A 规划：PostgreSQL、Redis、对象存储、长期记忆库。
- Phase 3B 规划：企业知识库同步、外部平台消息与文档映射。

**可观测性**

- Phase 1 当前状态：控制台日志、阶段回调、Verifier JSON。
- Phase 1.5 规划：SSE 事件流、Dashboard 时间线、产物状态；事件协议预留 DAG / SemanticStep 字段。
- Phase 2 规划：SemanticStep、结构化事件、Run Inspector 数据源。
- Phase 3A 规划：OpenTelemetry、指标看板、告警和审计日志。
- Phase 3B 规划：外部系统事件订阅、Webhook 回执、集成调用审计。

**部署与集成**

- Phase 1 当前状态：Streamlit Cloud / 本地运行。
- Phase 1.5 规划：FastAPI + React 同服务部署，云端可访问。
- Phase 2 规划：Docker Compose、环境隔离、任务队列预留。
- Phase 3A 规划：生产数据库、缓存、对象存储、稳定性治理。
- Phase 3B 规划：MCP Server 发布、飞书/钉钉上线、Webhook 与企业系统对接。

> ✅ = 已完成 🔨 = 当前优先 📋 = 后续规划

---

## 📋 输入格式

```json
{
  "productName": "飞书",
  "competitors": ["钉钉", "企业微信"],
  "dimensions": [
    {"name": "定价", "indicators": ["免费套餐", "付费套餐"]},
    {"name": "功能", "indicators": ["即时通讯", "文档协作"]},
    {"name": "用户体验", "indicators": ["界面设计", "操作流畅度"]}
  ],
  "analysisType": "SWOT"
}
```

---

## 🔬 核心技术亮点

1. **Provenance 溯源约束**：报告必须包含逐条 `[来源: URL]` 标注、可访问 URL 和 `Provenance 索引`；缺失则规则层直接判失败
2. **独立 Verification Agent**：使用 MiMo-V2.5-Pro，不继承撰写历史，主动找问题而非确认正确性
3. **最小重试闭环**：首次质检失败时，自动重跑 Writer + Verifier 一次；复检仍失败则返回质检问题并非零退出
4. **CrewAI 顺序执行**：低复杂度快速出活，Phase 2 可升级为并行 + 动态 DAG
5. **直连 MiMo API**：启动时清理系统代理环境变量，默认不走代理，避免本机代理设置干扰 API 调用

---

## 📁 项目结构

```
CompEyeAgent/
├── main.py                  # CLI 入口
├── app.py                   # Streamlit 可选入口
├── runner.py                # Phase 1 运行器：质检校验 + 最小重写闭环
├── crew/
│   ├── crew.py             # CrewAI Crew 组装
│   └── agents/
│       ├── collector.py     # 采集 Agent（MiMo-V2.5）
│       ├── analyzer.py      # 分析 Agent（MiMo-V2.5）
│       ├── writer.py        # 撰写 Agent（MiMo-V2.5）
│       └── verifier.py      # 质检 Agent（MiMo-V2.5-Pro）
├── tasks/                   # 四类 Task（含 context 依赖链）
├── models/
│   ├── schema.py           # 竞品输入 + Evidence/Claim/Finding/Issue 知识 Schema
│   └── provenance.py      # 溯源对象
├── config/
│   └── settings.py         # LLM 工厂函数
├── docs/
│   └── DESIGN.md           # 完整架构设计文档（含 12 项优化详解）
├── requirements.txt
└── README.md
```

---

## 📖 设计文档

完整的架构设计、12 项优化详细说明、分阶段路线图见 [docs/DESIGN.md](docs/DESIGN.md)。

---

## 🛠️ 环境变量

```bash
# MiMo API（OpenAI 兼容）
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=your_api_key_here

# 模型分配（可选，默认如下）
COLLECTOR_MODEL=mimo-v2.5
ANALYZER_MODEL=mimo-v2.5
WRITER_MODEL=mimo-v2.5
VERIFIER_MODEL=mimo-v2.5-pro
```


## 📜 许可证

MIT License — 欢迎开源共建！
