#!/usr/bin/env python3
"""竞品分析 Agent 协作系统 — Streamlit Demo."""

import time

import streamlit as st

import config.settings
from models.schema import CompetitorInput
from runner import run_analysis


st.set_page_config(
    page_title="CompEye Agent",
    page_icon="CE",
    layout="wide",
    initial_sidebar_state="collapsed",
)


DIMENSION_PRESETS = {
    "定价": ["免费套餐", "付费套餐", "套餐限制", "升级路径"],
    "功能": ["即时通讯", "文档协作", "视频会议", "自动化能力"],
    "用户体验": ["界面设计", "操作流畅度", "移动端体验", "学习成本"],
    "市场策略": ["目标客户", "获客方式", "生态合作", "品牌定位"],
    "性能": ["响应速度", "稳定性", "并发能力", "安全能力"],
}

STAGES = [
    ("collect", "Collector", "采集公开资料与来源"),
    ("analyze", "Analyzer", "提炼 SWOT / 对比结论"),
    ("write", "Writer", "生成可读 Markdown 报告"),
    ("verify", "Verifier", "检查幻觉、矛盾与证据"),
    ("rewrite", "Rewrite", "必要时重写并复检"),
    ("final", "Final", "整理最终结果"),
]

DEFAULTS = {
    "product_name": "飞书",
    "competitors": "钉钉, 企业微信",
    "dimensions": ["定价", "功能"],
    "custom_indicators": "免费套餐, 视频会议, 文档协作",
    "analysis_type": "SWOT",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

        :root {
            --ink: #14110f;
            --muted: #6d6258;
            --paper: #fbf7ef;
            --panel: #fffdf8;
            --line: #ded5c8;
            --accent: #0b6f6a;
            --accent-2: #d64b2a;
            --wash: #efe5d4;
        }

        .stApp {
            background:
                radial-gradient(circle at 20% 10%, rgba(214, 75, 42, .12), transparent 28rem),
                linear-gradient(135deg, #fbf7ef 0%, #f6efe4 52%, #e9f0ec 100%);
            color: var(--ink);
            font-family: "IBM Plex Sans", "Microsoft YaHei", sans-serif;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 1280px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .hero {
            border: 1px solid var(--line);
            background: rgba(255, 253, 248, .82);
            box-shadow: 0 24px 80px rgba(62, 47, 31, .12);
            padding: 28px 30px;
            margin-bottom: 22px;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(280px, .55fr);
            gap: 24px;
            align-items: end;
        }

        .kicker {
            color: var(--accent);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        .hero h1 {
            font-family: "Noto Serif SC", serif;
            font-size: clamp(36px, 5vw, 64px);
            line-height: 1.02;
            letter-spacing: 0;
            margin: 0 0 14px 0;
            color: var(--ink);
        }

        .hero p {
            color: var(--muted);
            font-size: 17px;
            line-height: 1.72;
            margin: 0;
            max-width: 760px;
        }

        .signal-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }

        .signal {
            border: 1px solid var(--line);
            background: #f8efe3;
            padding: 14px 12px;
            min-height: 84px;
        }

        .signal b {
            display: block;
            font-size: 24px;
            color: var(--accent-2);
            line-height: 1;
        }

        .signal span {
            display: block;
            color: var(--muted);
            font-size: 12px;
            margin-top: 8px;
        }

        .section-title {
            font-family: "Noto Serif SC", serif;
            font-size: 24px;
            margin: 8px 0 8px;
            color: var(--ink);
        }

        .soft-panel {
            border: 1px solid var(--line);
            background: rgba(255, 253, 248, .86);
            padding: 22px;
            min-height: 100%;
        }

        .stage-list {
            display: grid;
            gap: 10px;
            margin-top: 10px;
        }

        .stage {
            display: grid;
            grid-template-columns: 38px 1fr;
            gap: 12px;
            align-items: center;
            border: 1px solid var(--line);
            background: #fbf8f1;
            padding: 10px;
        }

        .stage .dot {
            width: 30px;
            height: 30px;
            display: grid;
            place-items: center;
            border: 1px solid var(--accent);
            color: var(--accent);
            font-weight: 700;
            font-size: 12px;
        }

        .stage.active {
            border-color: var(--accent);
            background: #e7f2ef;
        }

        .stage.done {
            border-color: rgba(11, 111, 106, .45);
            background: #f2f7f5;
        }

        .stage small {
            color: var(--muted);
            display: block;
            margin-top: 2px;
        }

        .stButton > button {
            border-radius: 0;
            min-height: 46px;
            font-weight: 700;
            border: 1px solid var(--ink);
        }

        .stButton > button[kind="primary"] {
            background: var(--ink);
            color: #fff;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stSelectbox"] div,
        div[data-testid="stMultiSelect"] div {
            border-radius: 0;
        }

        @media (max-width: 860px) {
            .hero-grid,
            .signal-row {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def build_inputs() -> dict:
    product_name = st.session_state.get("product_name", DEFAULTS["product_name"]).strip()
    competitors = parse_list(st.session_state.get("competitors", DEFAULTS["competitors"]))
    selected_dimensions = st.session_state.get("dimensions", DEFAULTS["dimensions"])
    custom_indicators = parse_list(
        st.session_state.get("custom_indicators", DEFAULTS["custom_indicators"])
    )
    analysis_type = st.session_state.get("analysis_type", DEFAULTS["analysis_type"])

    dimensions = []
    for dimension in selected_dimensions:
        indicators = list(dict.fromkeys(DIMENSION_PRESETS[dimension][:2] + custom_indicators))
        dimensions.append({"name": dimension, "indicators": indicators[:5]})

    return {
        "productName": product_name,
        "competitors": competitors,
        "dimensions": dimensions,
        "analysisType": analysis_type,
    }


def set_demo(product: str, competitors: str, dimensions: list[str], indicators: str) -> None:
    st.session_state.product_name = product
    st.session_state.competitors = competitors
    st.session_state.dimensions = dimensions
    st.session_state.custom_indicators = indicators
    st.session_state.analysis_type = "SWOT"


def render_stage_board(active_stage: str | None = None, done: set[str] | None = None) -> None:
    done = done or set()
    html = ['<div class="stage-list">']
    for index, (key, title, caption) in enumerate(STAGES, 1):
        state = "active" if key == active_stage else "done" if key in done else ""
        html.append(
            f'<div class="stage {state}"><div class="dot">{index}</div>'
            f'<div><b>{title}</b><small>{caption}</small></div></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_preview(inputs: dict) -> None:
    st.markdown("#### 本次分析 brief")
    st.json(inputs, expanded=False)


for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

inject_styles()

st.markdown(
    """
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="kicker">CompEye Agent / Live Review Console</div>
          <h1>让竞品分析像一次真实调研小组协作</h1>
          <p>输入产品、竞品和关注维度，四个 Agent 会依次完成公开资料采集、结构化分析、报告撰写和独立质检。页面会展示进度、最终报告和 Verifier 的问题清单。</p>
        </div>
        <div class="signal-row">
          <div class="signal"><b>4</b><span>专职 Agent</span></div>
          <div class="signal"><b>1x</b><span>失败自动重写</span></div>
          <div class="signal"><b>0</b><span>JSON 输入门槛</span></div>
        </div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([0.92, 1.08], gap="large")

with left:
    st.markdown('<div class="soft-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">配置分析任务</div>', unsafe_allow_html=True)

    demo_a, demo_b = st.columns(2)
    with demo_a:
        if st.button("飞书 vs 钉钉", use_container_width=True):
            set_demo("飞书", "钉钉", ["定价", "功能"], "免费套餐, 视频会议, 文档协作")
    with demo_b:
        if st.button("豆包 vs Kimi", use_container_width=True):
            set_demo("豆包", "Kimi, 通义千问", ["功能", "用户体验"], "长文本, 多模态, 搜索能力")

    st.text_input("目标产品", key="product_name")
    st.text_input("竞品名称，用逗号分隔", key="competitors")
    st.multiselect(
        "关注维度",
        options=list(DIMENSION_PRESETS.keys()),
        key="dimensions",
    )
    st.text_area(
        "重点指标，用逗号分隔",
        key="custom_indicators",
        height=88,
    )
    st.selectbox(
        "报告形式",
        ["SWOT", "对比表格", "综合报告"],
        key="analysis_type",
    )

    quick_mode = st.toggle("快速演示模式：只跑一次质检，不自动重写", value=True)
    run_button = st.button("开始分析", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="soft-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">执行进展</div>', unsafe_allow_html=True)
    stage_slot = st.empty()
    status_slot = st.empty()
    progress_slot = st.empty()
    preview_slot = st.empty()
    with stage_slot:
        render_stage_board()
    st.markdown("</div>", unsafe_allow_html=True)

inputs = build_inputs()
with preview_slot:
    render_preview(inputs)

if run_button:
    try:
        validated = CompetitorInput(**inputs).model_dump()
    except Exception as exc:
        st.error(f"输入不完整或不合法：{exc}")
        st.stop()

    stage_order = {key: idx for idx, (key, _, _) in enumerate(STAGES)}
    done_stages: set[str] = set()

    def update_progress(stage: str, message: str) -> None:
        for key, _, _ in STAGES:
            if stage_order[key] < stage_order.get(stage, 0):
                done_stages.add(key)
        with stage_slot:
            render_stage_board(active_stage=stage, done=done_stages)
        status_slot.info(message)
        progress_slot.progress(
            min((stage_order.get(stage, 0) + 1) / len(STAGES), 0.95),
            text=message,
        )
        time.sleep(0.2)

    with st.spinner("Agent 正在协作，请稍候..."):
        update_progress("collect", "Collector 正在采集公开信息")
        result = run_analysis(
            validated,
            allow_retry=not quick_mode,
            progress_callback=update_progress,
        )

    with stage_slot:
        render_stage_board(done={key for key, _, _ in STAGES})
    progress_slot.progress(1.0, text="分析完成")

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("质检状态", "通过" if result.passed else "未通过")
    c2.metric("自动重写", "是" if result.retried else "否")
    c3.metric("模式", "快速演示" if quick_mode else "严格复检")

    if result.passed:
        st.success("报告通过质检。")
    else:
        st.warning("报告已生成，但 Verifier 仍发现证据或逻辑问题，适合展示独立质检能力。")

    report_tab, verify_tab, brief_tab = st.tabs(["分析报告", "质检结果", "任务 brief"])
    with report_tab:
        st.markdown(result.report)
    with verify_tab:
        st.code(result.verifier_result, language="json")
    with brief_tab:
        st.json(validated)
