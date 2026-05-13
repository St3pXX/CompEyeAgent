# 竞品分析 Agent 协作系统

> 多 Agent 协同，自动完成竞品信息采集 → 分析 → 报告生成，每条结论可溯源。

[![CI](https://github.com/your-username/competitor-analysis-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/competitor-analysis-agent)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

---

## ✨ 设计亮点

- 🧠 **借鉴 Claude Code 源码思想**：Coordinator 模式、Scratchpad 共享目录、独立 Verification Agent、工具层强制溯源
- 🤖 **MiMo 模型分层**：V2.5（高速低成本）处理采集/分析/撰写，V2.5-Pro（强推理）专职质检
- 🔍 **全链路可观测**：每个 Agent 的输入/输出/决策过程实时打印，支持流式透出
- 📎 **溯源强制约束**：每条分析结论附带来源 URL + 原文片段，模型不提供则判定不合格
- ✅ **交叉审查闭环**：独立 Verification Agent（不继承历史）防确认偏误，置信度分级处理

---

## 🏗️ 系统架构

```
用户输入（CLI/Streamlit）
        │
        ▼
┌──────────────────────────────────────────┐
│            CrewAI Crew                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │
│  │Collector│→ │Analyzer │→ │ Writer  │→ │Verifier│ │
│  │ MiMo-25 │  │ MiMo-25 │  │ MiMo-25 │  │MiMo-Pro│ │
│  └─────────┘  └─────────┘  └─────────┘  └────────┘ │
└──────────────────────────────────────────┘
        │
        ▼
   最终报告（Markdown）+ 溯源附件 + 控制台日志
```

**Agent 分工：**

| Agent | 模型 | 职责 |
|-------|------|------|
| 搜集专家 | MiMo-V2.5 | 联网搜索采集竞品公开信息 |
| 数据分析师 | MiMo-V2.5 | SWOT / 对比结构化分析 |
| 报告撰写师 | MiMo-V2.5 | 生成 Markdown 报告 |
| 质量检测师 | MiMo-V2.5-Pro | 独立校验（逻辑矛盾/幻觉/缺失证据） |

---

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/competitor-analysis-agent.git
cd competitor-analysis-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（创建 .env 文件）
echo "MIMO_BASE_URL=https://api.minimax.chat/v1" > .env
echo "MIMO_API_KEY=your_api_key_here" >> .env

# 4. 运行
python main.py '{"productName":"飞书","competitors":["钉钉","企业微信"],"dimensions":[{"name":"定价","indicators":["免费套餐"]}]}'
```

**可选：Streamlit 界面**
```bash
streamlit run app.py
```

---

## 📖 详细设计

见 [DESIGN.md](docs/superpowers/specs/2026-05-13-competitor-analysis-agent-design.md) — 包含完整的架构图、数据模型、12 项优化详细设计、Claude Code 思想映射表。

---

## 🎯 设计哲学：借鉴 Claude Code 源码的工程思想

本系统的多 Agent 协作设计深度借鉴了 Claude Code 源码中已验证的工程哲学：

| Claude Code 思想 | 在本系统中的落地 |
|----------------|----------------|
| **Coordinator 模式** | Phase 2 将引入独立 Coordinator Agent，专职拆解任务、调度子 Agent |
| **Scratchpad 共享目录** | Phase 2 文件系统 Scratchpad，采集写入 JSON，分析直接读取 |
| **工具层强制溯源** | Agent Prompt 强制要求 provenance 对象，Verification Agent 检查缺失 |
| **独立 Verification Agent** | MiMo-V2.5-Pro 模型，不传递撰写者对话历史，防确认偏误 |
| **流式 Generator 透出** | Phase 1 verbose=True，Phase 2 SSE 流式推送 |
| **分层可观测性** | 控制台日志（语义追踪雏形），Phase 2 接入 OpenTelemetry |

---

## 📋 输入格式

```json
{
  "productName": "产品名称",
  "competitors": ["竞品A", "竞品B"],
  "dimensions": [
    {"name": "定价", "indicators": ["免费套餐", "付费套餐"]},
    {"name": "功能", "indicators": ["即时通讯", "文档协作"]}
  ],
  "analysisType": "SWOT"
}
```

---

## 📁 项目结构

```
competitor_analysis/
├── main.py                  # CLI 入口
├── app.py                   # Streamlit 可选入口
├── crew/
│   ├── crew.py             # CrewAI Crew 定义
│   └── agents/
│       ├── collector.py     # 采集 Agent（MiMo-V2.5）
│       ├── analyzer.py      # 分析 Agent（MiMo-V2.5）
│       ├── writer.py        # 撰写 Agent（MiMo-V2.5）
│       └── verifier.py      # 质检 Agent（MiMo-V2.5-Pro）
├── tasks/
│   ├── collect_task.py
│   ├── analyze_task.py
│   ├── write_task.py
│   └── verify_task.py
├── models/
│   ├── schema.py           # 竞品输入 Pydantic 模型
│   └── provenance.py       # 溯源对象
├── config/
│   └── settings.py         # LLM 配置
├── docs/                    # 设计文档
└── requirements.txt
```

---

## 🔧 环境变量

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

MIT License