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
| **工具层强制溯源** | 每条采集数据必须附带 `source_references`，缺失则质检不通过 |
| **流式 Generator 透出** | Phase 1 使用 `verbose=True` 控制台实时打印，Phase 2 升级 SSE |
| **分层可观测性** | 控制台日志（L3 语义追踪雏形）+ OTel 指标（Phase 2） |

**本质区别**：普通多 Agent 脚本是"串在一起"，我们的系统是"真正协同"——每个 Agent 职责单一、独立判断、通过结构化数据通信。

---

## 🏗️ 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户 / CLI / Streamlit                     │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────┐
│                     CrewAI Crew（顺序执行）                       │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  搜集专家    │ →  │  数据分析师  │ →  │  报告撰写师  │ →  │  质量检测师  │   │
│  │  Collector   │    │   Analyzer  │    │    Writer    │    │   Verifier   │   │
│  │              │    │              │    │              │    │              │   │
│  │  MiMo-V2.5   │    │  MiMo-V2.5   │    │  MiMo-V2.5   │    │ MiMo-V2.5-Pro│   │
│  │  (采集专家)  │    │  (结构分析)  │    │  (报告生成)  │    │  (独立校验)  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         ✅ Markdown 报告
                         📎 Provenance 溯源索引
                         🔍 控制台可观测日志
```

---

## 🤖 模型分工（MiMo 系列）

| Agent | 模型 | 职责 | 为什么用它 |
|-------|------|------|-----------|
| **Collector** | MiMo-V2.5 | 联网搜索采集公开信息 | 性价比高，联网搜索能力强 |
| **Analyzer** | MiMo-V2.5 | SWOT / 对比结构化分析 | 日常分析任务，V2.5 足够 |
| **Writer** | MiMo-V2.5 | 生成 Markdown 报告 | 格式化输出，V2.5 足够 |
| **Verifier** | MiMo-V2.5-Pro | **独立校验**（逻辑矛盾/幻觉/缺失证据） | 100万 Token 上下文 + 复杂推理，Pro 专属 |

> MiMo-V2.5-Pro 仅用于需要深度逻辑校验的质检环节，实现"让专业的做专业的事"。

---

## 🚀 在线体验（让评委立刻跑起来！）

### 方式一：Colab 一键运行（推荐！）

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/)

**或手动在 Colab 中执行：**
```python
# 克隆仓库
!git clone https://github.com/St3pXX/CompEyeAgent.git
%cd CompEyeAgent

# 安装依赖
!pip install -r requirements.txt

# 配置 API Key（在 Colab "🔑" 图标中添加环境变量)
import os
os.environ["MIMO_BASE_URL"] = "https://api.minimax.chat/v1"  # 或你的 MiMo 地址
os.environ["MIMO_API_KEY"] = "你的_API_KEY"

# 运行示例
!python main.py '{"productName":"飞书","competitors":["钉钉"],"dimensions":[{"name":"定价","indicators":["免费套餐"]}]}'
```

### 方式二：本地运行

```bash
# 1. 克隆
git clone https://github.com/St3pXX/CompEyeAgent.git
cd CompEyeAgent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 MIMO_API_KEY

# 4. 运行
python main.py '{"productName":"飞书","competitors":["钉钉"],"dimensions":[{"name":"定价","indicators":["免费套餐"]}]}'
```

### 方式三：Streamlit 界面

```bash
streamlit run app.py
# 浏览器打开 http://localhost:8501
```

---

## 📊 执行计划与当前进度

| 阶段 | 内容 | 状态 | 说明 |
|------|------|------|------|
| **Phase 1 (MVP)** | 四 Agent 顺序链路 + CLI + Streamlit | ✅ 已完成 | 可运行，代码已开源 |
| **Phase 2** | 自研 Coordinator 主循环 + Scratchpad 文件系统 + SSE 流式输出 | 🔨 规划中 | 动态 DAG + 工具层强制溯源 |
| **Phase 3** | 长期记忆库 + 完整 OTel 可观测性 + 权限系统 | 📋 规划中 | 企业级扩展 |

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

1. **Provenance 溯源约束**：每条分析结论必须附带 `source_references`（URL + 原文片段），无溯源则质检不通过
2. **独立 Verification Agent**：使用 MiMo-V2.5-Pro，不继承撰写历史，主动找问题而非确认正确性
3. **置信度分级处理**：confidence ≥ 90 通过，60-90 待复核，< 60 触发重试
4. **CrewAI 顺序执行**：低复杂度快速出活，Phase 2 可升级为并行 + 动态 DAG

---

## 📁 项目结构

```
CompEyeAgent/
├── main.py                  # CLI 入口
├── app.py                   # Streamlit 可选入口
├── crew/
│   ├── crew.py             # CrewAI Crew 组装
│   └── agents/
│       ├── collector.py     # 采集 Agent（MiMo-V2.5）
│       ├── analyzer.py      # 分析 Agent（MiMo-V2.5）
│       ├── writer.py        # 撰写 Agent（MiMo-V2.5）
│       └── verifier.py      # 质检 Agent（MiMo-V2.5-Pro）
├── tasks/                   # 四类 Task（含 context 依赖链）
├── models/
│   ├── schema.py           # 竞品输入 Pydantic 模型
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

完整的架构设计、12 项优化详细说明、分阶段路线图见 [DESIGN.md](docs/superpowers/specs/2026-05-13-competitor-analysis-agent-design.md)。

---

## 🛠️ 环境变量

```bash
# MiMo API（OpenAI 兼容）
MIMO_BASE_URL=https://api.minimax.chat/v1
MIMO_API_KEY=your_api_key_here

# 模型分配（可选，默认如下）
COLLECTOR_MODEL=xiaomi/mimo-v2.5
ANALYZER_MODEL=xiaomi/mimo-v2.5
WRITER_MODEL=xiaomi/mimo-v2.5
VERIFIER_MODEL=xiaomi/mimo-v2.5-pro
```

---

## 📜 许可证

MIT License — 欢迎开源共建！