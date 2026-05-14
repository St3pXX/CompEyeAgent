#!/usr/bin/env python3
"""CompEye Agent Streamlit demo."""

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
    ("collect", "Collect", "采集公开资料"),
    ("analyze", "Analyze", "生成结构化结论"),
    ("write", "Write", "撰写 Markdown 报告"),
    ("verify", "Verify", "独立校验证据"),
    ("rewrite", "Rewrite", "必要时重写"),
    ("final", "Done", "输出结果"),
]

SAMPLES = {
    "飞书 vs 钉钉": {
        "product_name": "飞书",
        "competitors": "钉钉, 企业微信",
        "dimensions": ["定价", "功能"],
        "custom_indicators": "免费套餐, 视频会议, 文档协作",
        "analysis_type": "SWOT",
    },
    "豆包 vs Kimi": {
        "product_name": "豆包",
        "competitors": "Kimi, 通义千问",
        "dimensions": ["功能", "用户体验"],
        "custom_indicators": "长文本, 多模态, 搜索能力",
        "analysis_type": "SWOT",
    },
    "Notion AI vs 飞书妙记": {
        "product_name": "Notion AI",
        "competitors": "飞书妙记, 腾讯文档智能助手",
        "dimensions": ["功能", "定价", "用户体验"],
        "custom_indicators": "AI 摘要, 协作工作流, 付费策略",
        "analysis_type": "综合报告",
    },
}

DEFAULTS = SAMPLES["飞书 vs 钉钉"]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Noto+Sans+SC:wght@400;500;700&display=swap');

        :root {
            --bg: #f8fafd;
            --surface: #ffffff;
            --surface-2: #f1f4f9;
            --line: #dfe4ee;
            --text: #1f1f1f;
            --muted: #5f6368;
            --blue: #1a73e8;
            --blue-soft: #e8f0fe;
            --green: #137333;
            --red: #b3261e;
            --chip: #edf2fa;
            --shadow: 0 1px 2px rgba(60, 64, 67, .18), 0 1px 3px rgba(60, 64, 67, .12);
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
            font-family: "Google Sans", "Noto Sans SC", sans-serif;
        }

        [data-testid="stHeader"] {
            background: rgba(248, 250, 253, .92);
            border-bottom: 1px solid var(--line);
        }

        .block-container {
            max-width: 1440px;
            padding: 1.1rem 1.4rem 2rem;
        }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 14px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo {
            width: 34px;
            height: 34px;
            border-radius: 10px;
            display: grid;
            place-items: center;
            background: linear-gradient(135deg, #1a73e8, #5e97f6);
            color: #fff;
            font-weight: 700;
            letter-spacing: 0;
        }

        .brand-title {
            font-size: 18px;
            font-weight: 700;
            line-height: 1.1;
        }

        .brand-subtitle {
            color: var(--muted);
            font-size: 12px;
            margin-top: 1px;
        }

        .top-actions {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid var(--line);
            background: var(--surface);
            color: var(--muted);
            border-radius: 999px;
            padding: 7px 11px;
            font-size: 12px;
            box-shadow: var(--shadow);
        }

        .panel {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 18px;
            box-shadow: var(--shadow);
        }

        .panel-pad {
            padding: 16px;
        }

        .left-nav {
            position: sticky;
            top: 76px;
        }

        .nav-heading {
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .02em;
            margin: 4px 0 10px;
        }

        .sample-card {
            border: 1px solid transparent;
            border-radius: 14px;
            background: var(--surface-2);
            padding: 12px;
            margin-bottom: 10px;
        }

        .sample-card strong {
            display: block;
            font-size: 13px;
            margin-bottom: 4px;
        }

        .sample-card span {
            color: var(--muted);
            display: block;
            font-size: 12px;
            line-height: 1.45;
        }

        .prompt-card {
            padding: 18px;
            min-height: 328px;
        }

        .prompt-title {
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 0;
            margin: 0 0 6px;
        }

        .prompt-caption {
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 16px;
        }

        .section-label {
            font-size: 13px;
            color: var(--muted);
            font-weight: 700;
            margin: 0 0 10px;
        }

        .run-settings {
            position: sticky;
            top: 76px;
        }

        .stage-list {
            display: grid;
            gap: 8px;
            margin-top: 8px;
        }

        .stage-row {
            display: grid;
            grid-template-columns: 26px 1fr;
            gap: 10px;
            align-items: center;
            padding: 9px;
            border-radius: 13px;
            background: transparent;
            border: 1px solid transparent;
        }

        .stage-dot {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            border: 1px solid var(--line);
            color: var(--muted);
            font-size: 11px;
            font-weight: 700;
            background: #fff;
        }

        .stage-row.active {
            background: var(--blue-soft);
            border-color: #c6dafc;
        }

        .stage-row.active .stage-dot {
            background: var(--blue);
            border-color: var(--blue);
            color: #fff;
        }

        .stage-row.done .stage-dot {
            background: #e6f4ea;
            border-color: #ceead6;
            color: var(--green);
        }

        .stage-row b {
            display: block;
            font-size: 13px;
        }

        .stage-row small {
            display: block;
            color: var(--muted);
            font-size: 11px;
            margin-top: 1px;
        }

        .result-shell {
            margin-top: 16px;
        }

        .metric-strip {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin: 14px 0;
        }

        .metric-card {
            border: 1px solid var(--line);
            border-radius: 16px;
            background: var(--surface);
            padding: 13px 14px;
        }

        .metric-card span {
            color: var(--muted);
            display: block;
            font-size: 12px;
        }

        .metric-card b {
            display: block;
            font-size: 22px;
            margin-top: 5px;
        }

        .stButton > button {
            border-radius: 999px;
            min-height: 38px;
            font-weight: 600;
            border: 1px solid var(--line);
        }

        .stButton > button[kind="primary"] {
            background: var(--blue);
            border-color: var(--blue);
            color: #fff;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            border-radius: 14px;
            border-color: var(--line);
            background: #fff;
        }

        div[data-testid="stMultiSelect"] div,
        div[data-testid="stSelectbox"] div {
            border-radius: 14px;
        }

        [data-testid="stTabs"] button {
            font-weight: 600;
        }

        @media (max-width: 1100px) {
            .left-nav,
            .run-settings {
                position: static;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def apply_sample(name: str) -> None:
    for key, value in SAMPLES[name].items():
        st.session_state[key] = value


def build_inputs() -> dict:
    dimensions = []
    custom_indicators = parse_list(st.session_state.custom_indicators)
    for dimension in st.session_state.dimensions:
        indicators = list(dict.fromkeys(DIMENSION_PRESETS[dimension][:2] + custom_indicators))
        dimensions.append({"name": dimension, "indicators": indicators[:5]})

    return {
        "productName": st.session_state.product_name.strip(),
        "competitors": parse_list(st.session_state.competitors),
        "dimensions": dimensions,
        "analysisType": st.session_state.analysis_type,
    }


def render_stage_board(active_stage: str | None = None, done: set[str] | None = None) -> None:
    done = done or set()
    html = ['<div class="stage-list">']
    for index, (key, title, caption) in enumerate(STAGES, 1):
        state = "active" if key == active_stage else "done" if key in done else ""
        mark = "✓" if key in done else str(index)
        html.append(
            f'<div class="stage-row {state}"><div class="stage-dot">{mark}</div>'
            f'<div><b>{title}</b><small>{caption}</small></div></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_metric(label: str, value: str) -> str:
    return f'<div class="metric-card"><span>{label}</span><b>{value}</b></div>'


def initialize_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)


initialize_state()
inject_styles()

st.markdown(
    """
    <div class="topbar">
      <div class="brand">
        <div class="logo">CE</div>
        <div>
          <div class="brand-title">CompEye Agent</div>
          <div class="brand-subtitle">Multi-agent competitor analysis workspace</div>
        </div>
      </div>
      <div class="top-actions">
        <span class="pill">MiMo V2.5 + Pro</span>
        <span class="pill">Evidence-first report</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

left_col, center_col, right_col = st.columns([0.8, 1.75, 1.0], gap="medium")

with left_col:
    st.markdown('<section class="panel panel-pad left-nav">', unsafe_allow_html=True)
    st.markdown('<div class="nav-heading">Examples</div>', unsafe_allow_html=True)
    for sample_name, sample in SAMPLES.items():
        st.markdown(
            f"""
            <div class="sample-card">
              <strong>{sample_name}</strong>
              <span>{sample["custom_indicators"]}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"Use {sample_name}", key=f"sample_{sample_name}", use_container_width=True):
            apply_sample(sample_name)
            st.rerun()

    st.markdown('<div class="nav-heading" style="margin-top:16px;">Demo notes</div>', unsafe_allow_html=True)
    st.caption("快速演示模式会缩短等待时间；严格模式会在质检失败时自动重写一次。")
    st.caption("Verifier 不继承 Writer 历史，会主动寻找幻觉、矛盾和缺失证据。")
    st.markdown("</section>", unsafe_allow_html=True)

with center_col:
    st.markdown('<section class="panel prompt-card">', unsafe_allow_html=True)
    st.markdown('<div class="prompt-title">Create an analysis run</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="prompt-caption">Configure the business question like a prompt, then run the agent crew.</div>',
        unsafe_allow_html=True,
    )

    a, b = st.columns([1, 1], gap="small")
    with a:
        st.text_input("Target product", key="product_name")
    with b:
        st.text_input("Competitors", key="competitors", help="Use commas to separate competitors.")

    st.multiselect("Analysis dimensions", options=list(DIMENSION_PRESETS.keys()), key="dimensions")
    st.text_area("Focus indicators", key="custom_indicators", height=96)
    st.selectbox("Output format", ["SWOT", "对比表格", "综合报告"], key="analysis_type")

    run_button = st.button("Run analysis", type="primary", use_container_width=True)
    st.markdown("</section>", unsafe_allow_html=True)

    result_container = st.container()

with right_col:
    st.markdown('<section class="panel panel-pad run-settings">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Run settings</div>', unsafe_allow_html=True)
    quick_mode = st.toggle("Fast demo mode", value=True, help="Skip the automatic rewrite pass.")
    show_brief = st.toggle("Show generated brief", value=True)
    inputs = build_inputs()
    if show_brief:
        st.json(inputs, expanded=False)

    st.markdown('<div class="section-label" style="margin-top:16px;">Agent status</div>', unsafe_allow_html=True)
    stage_slot = st.empty()
    status_slot = st.empty()
    progress_slot = st.empty()
    with stage_slot:
        render_stage_board()
    st.markdown("</section>", unsafe_allow_html=True)

if run_button:
    try:
        validated = CompetitorInput(**build_inputs()).model_dump()
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
            min((stage_order.get(stage, 0) + 1) / len(STAGES), 0.96),
            text=message,
        )
        time.sleep(0.15)

    with result_container:
        with st.spinner("Running agent crew..."):
            update_progress("collect", "Collector is gathering public evidence")
            result = run_analysis(
                validated,
                allow_retry=not quick_mode,
                progress_callback=update_progress,
            )

        with stage_slot:
            render_stage_board(done={key for key, _, _ in STAGES})
        status_slot.success("Run complete")
        progress_slot.progress(1.0, text="Run complete")

        st.markdown('<div class="result-shell">', unsafe_allow_html=True)
        status_text = "Passed" if result.passed else "Needs review"
        retry_text = "Yes" if result.retried else "No"
        mode_text = "Fast" if quick_mode else "Strict"
        st.markdown(
            '<div class="metric-strip">'
            + render_metric("Verifier", status_text)
            + render_metric("Rewrite pass", retry_text)
            + render_metric("Mode", mode_text)
            + "</div>",
            unsafe_allow_html=True,
        )

        if result.passed:
            st.success("Verifier accepted the report.")
        else:
            st.warning("Report generated. Verifier found evidence or reasoning issues for review.")

        report_tab, verify_tab, brief_tab = st.tabs(["Report", "Verifier JSON", "Brief"])
        with report_tab:
            st.markdown(result.report)
        with verify_tab:
            st.code(result.verifier_result, language="json")
        with brief_tab:
            st.json(validated)
        st.markdown("</div>", unsafe_allow_html=True)
