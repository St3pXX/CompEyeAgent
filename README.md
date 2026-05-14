# CompEye Agent — AI 竞品分析 Agent 协作系统

> 多 Agent 协同，自动完成竞品信息采集 → 分析 → 报告生成，每条结论可溯源。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🎯 一句话定位

**一个借鉴 Claude Code 工程思想构建的多 Agent 竞品分析系统**，通过采集、分析、撰写、质检四个专职 Agent 的顺序协作，实现从公开信息采集到结构化报告的全链路自动化，同时保证**每条结论可溯源、每个决策可观测**。

---

## 🧠 设计哲学：为什么说我们借鉴了 Claude Code？

本系统并非简单堆砌 AI Agent，而是深度借鉴了 Claude Code（51.2 万行 TypeScript 工程实践）的核心设计哲学：

| Claude Code 思想 | 本系统如何落地 |
|----------------|---------------|
| **主循环 + 工具调用** | Coordinator 主循环动态调度四类工具，Agent 不直接执行，只通过工具协作 |
| **Scratchpad 共享目录** | Phase 2 将实现文件系统 Scratchpad，采集数据旁路传递，避免上下文爆炸 |
| **独立 Verification Agent** | 质检 Agent 使用 MiMo-V2.5-Pro，**不继承撰写者历史**，独立判断，防确认偏误 |
| **规则层溯源校验** | `runner.py` 会检查最终报告是否包含来源标注 / URL / provenance，缺失则判失败 |
| **流式 Generator 透出** | Phase 1 使用 `verbose=True` 控制台实时打印，Phase 2 升级 SSE |
| **分层可观测性** | 控制台日志（L3 语义追踪雏形）+ OTel 指标（Phase 2） |

**本质区别**：普通多 Agent 脚本是"串在一起"，我们的系统是"真正协同"——每个 Agent 职责单一、独立判断、通过结构化数据通信。

---

## 🏗️ 最终目标架构

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                         Web Demo / CLI / Future API                         │
│                 表单化输入 · 实时进度 · Run Inspector · 报告导出            │
└──────────────────────────────────────┬─────────────────────────────────────┘
                                       │  SSE / async events
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
│                               Scratchpad                                    │
│ raw/ 原始采集 · evidence/ 证据 · claims/ 论点 · drafts/ 草稿 ·              │
│ verification/ 质检结果 · tasks/ DAG 状态 · provenance/ 溯源索引             │
└──────────────────────────────────────┬─────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼─────────────────────────────────────┐
│                             Observability                                   │
│ 产品事件 · Token/延迟指标 · SemanticStep 决策链 · 每条结论可追溯证据       │
└────────────────────────────────────────────────────────────────────────────┘
```

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

Phase 1 的定位是跑通可演示 MVP：证明四类专职 Agent 能协作完成竞品资料采集、分析、撰写和独立质检，并通过规则层 guard 保证报告至少具备逐条来源标注、可访问 URL 和 provenance 索引。

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

网页端面向评审演示做了产品化输入，不需要手写 JSON：

- 输入目标产品和竞品名称
- 勾选分析维度，填写重点指标
- 点击示例按钮一键填充演示案例
- 点击开始分析后，可看到 Collector / Analyzer / Writer / Verifier 的阶段进度
- 默认启用快速演示模式，只跑一次完整质检以缩短等待时间；关闭后会启用“失败自动重写一次”的严格复检链路

---

## 📊 阶段进展

| 阶段 | 状态 | 当前交付 | 目标能力 |
|------|------|----------|----------|
| **Phase 1: MVP Demo** | ✅ 已完成 | Streamlit 在线 Demo、CLI、四 Agent 顺序链路、MiMo 原生搜索、结构化输入、Verifier 质检、最小重写闭环、规则层 provenance guard | 可运行、可展示、可解释 |
| **Phase 2: DAG + Scratchpad** | 🔨 规划中 | 自研 Coordinator、按 `竞品 × 维度 × 指标` 拆分 DAG、Scratchpad 中间产物、工具层强制 provenance、SSE 流式状态、Run Inspector | 更贴近真实数字调研小组 |
| **Phase 3: Enterprise Ready** | 📋 规划中 | 长期记忆库、完整 OTel 指标、权限系统、多模型 fallback、人工复核队列、Dashboard | 企业级稳定性与可治理性 |

> ✅ = 已完成 🔨 = 进行中 📋 = 规划中

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

### API 连通性测试

```bash
python test_api.py
```

预期返回 `Status: 200`。脚本会读取 `.env`，并使用 `requests.Session(trust_env=False)` 直连 MiMo API，不读取系统代理设置。

---

## 📜 许可证

MIT License — 欢迎开源共建！
