#!/usr/bin/env python3
"""竞品分析 Agent 协作系统 — Streamlit 可选入口"""

import streamlit as st
import json
from crew import analysis_crew
from models.schema import CompetitorInput

st.set_page_config(page_title="AI 竞品分析 Agent 系统", page_icon="🔍")

st.title("🔍 AI 竞品分析 Agent 协作系统")
st.markdown("多 Agent 协同，自动完成竞品信息采集 → 分析 → 报告生成，每条结论可溯源。")

st.markdown("---")

st.markdown("### 📋 输入竞品分析需求")

example = {
    "productName": "飞书",
    "competitors": ["钉钉", "企业微信"],
    "dimensions": [
        {"name": "定价", "indicators": ["免费套餐", "付费套餐"]},
        {"name": "功能", "indicators": ["即时通讯", "文档协作", "视频会议"]},
    ],
    "analysisType": "SWOT",
}

user_input = st.text_area(
    "输入 JSON 格式的竞品分析需求",
    value=json.dumps(example, ensure_ascii=False, indent=2),
    height=250,
)

st.markdown("---")

col1, col2 = st.columns([1, 4])
with col1:
    run_button = st.button("🚀 开始分析", type="primary", use_container_width=True)

with col2:
    st.caption("MiMo-V2.5（采集/分析/撰写）+ MiMo-V2.5-Pro（质检）")

if run_button:
    try:
        inputs = json.loads(user_input)
        validated = CompetitorInput(**inputs).model_dump()

        st.markdown(f"**目标产品:** {validated['productName']}")
        st.markdown(f"**竞品:** {', '.join(validated['competitors'])}")
        st.markdown(f"**维度:** {', '.join(d['name'] for d in validated['dimensions'])}")

        st.markdown("---")
        st.markdown("### 🤖 Agent 协作分析中...")

        with st.spinner("Collector → Analyzer → Writer → Verifier"):
            result = analysis_crew.kickoff(inputs=validated)

        st.markdown("---")
        st.markdown("### 📊 分析结果")
        st.markdown(result)

    except json.JSONDecodeError as e:
        st.error(f"JSON 解析错误: {e}")
    except Exception as e:
        st.error(f"错误: {e}")

st.markdown("---")
st.caption("设计思想：借鉴 Claude Code 源码的 Coordinator 模式 + 独立 Verification Agent")