#!/usr/bin/env python3
"""CompEye Agent Streamlit demo."""

import time
from html import escape

import streamlit as st

import config.settings
from models.schema import CompetitorInput
from runner import run_analysis


st.set_page_config(
    page_title="CompEye Agent Demo",
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

INDICATOR_OPTIONS = list(dict.fromkeys(item for items in DIMENSION_PRESETS.values() for item in items)) + [
    "AI 助手",
    "知识库",
    "开放 API",
    "私有化部署",
]

STAGES = [
    ("collect", "Collect", "公开资料采集", "为每个竞品和指标寻找公开证据"),
    ("analyze", "Analyze", "结构化分析", "把证据整理为 SWOT / 对比结论"),
    ("write", "Write", "报告撰写", "生成可读 Markdown 竞品报告"),
    ("verify", "Verify", "独立质检", "校验幻觉、矛盾、缺失来源"),
    ("rewrite", "Rewrite", "自动修复", "按质检意见最小重写一次"),
    ("final", "Done", "产物交付", "输出报告、质检 JSON 和输入 brief"),
]

DEFAULTS = {
    "product_name": "飞书",
    "competitors": "钉钉, 企业微信",
    "selected_dimensions": ["定价", "功能", "用户体验"],
    "custom_dimensions": "",
    "selected_indicators": ["免费套餐", "文档协作", "视频会议", "AI 助手"],
    "custom_indicators": "",
    "analysis_type": "SWOT",
}
WORKSPACE_PANEL_HEIGHT = 560


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #eef3f8;
            --ink: #172033;
            --muted: #667085;
            --soft: #f8fafc;
            --panel: rgba(255, 255, 255, .86);
            --line: rgba(119, 130, 153, .22);
            --blue: #2563eb;
            --blue-2: #88b7ff;
            --mint: #20b486;
            --rose: #ef6f8f;
            --amber: #f59e0b;
            --violet: #8b5cf6;
            --shadow: 0 18px 50px rgba(38, 52, 83, .12);
        }

        .stApp {
            background:
                radial-gradient(circle at 18% 8%, rgba(136, 183, 255, .24), transparent 30%),
                linear-gradient(180deg, #f6f8fb 0%, var(--bg) 46%, #f8fafc 100%);
            color: var(--ink);
        }

        html,
        body,
        [data-testid="stAppViewContainer"],
        .stApp {
            height: 100vh;
            overflow: hidden;
        }

        [data-testid="stHeader"] {
            display: none !important;
        }

        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        .stDeployButton,
        #MainMenu,
        footer {
            display: none !important;
        }

        .block-container {
            max-width: 1480px;
            padding: .55rem 1.2rem .8rem;
            max-height: 100vh;
            overflow: hidden;
        }

        [data-testid="stVerticalBlock"] {
            gap: .7rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 22px;
        }

        [data-testid="stVerticalBlockBorderWrapper"] > div {
            border-color: var(--line);
            background: var(--panel);
            box-shadow: var(--shadow);
            backdrop-filter: blur(22px);
        }

        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {
            gap: .55rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"]::-webkit-scrollbar,
        [data-testid="stVerticalBlock"]::-webkit-scrollbar,
        div[data-testid="stVerticalBlockBorderWrapper"] > div::-webkit-scrollbar,
        .stMarkdown::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        [data-testid="stVerticalBlockBorderWrapper"]::-webkit-scrollbar-thumb,
        [data-testid="stVerticalBlock"]::-webkit-scrollbar-thumb,
        div[data-testid="stVerticalBlockBorderWrapper"] > div::-webkit-scrollbar-thumb,
        .stMarkdown::-webkit-scrollbar-thumb {
            background: rgba(102, 112, 133, .28);
            border-radius: 999px;
        }

        .demo-topbar,
        .panel,
        .composer,
        .sample-card,
        .metric-card {
            border: 1px solid var(--line);
            background: var(--panel);
            box-shadow: var(--shadow);
            backdrop-filter: blur(22px);
        }

        .demo-topbar {
            min-height: 58px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 18px;
            border-radius: 20px;
            margin-bottom: 14px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-mark {
            width: 38px;
            height: 38px;
            border-radius: 12px;
            display: grid;
            place-items: center;
            color: #fff;
            font-weight: 800;
            background: linear-gradient(135deg, #172033 0%, #2563eb 62%, #20b486 100%);
        }

        .brand-title {
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 0;
        }

        .brand-subtitle {
            color: var(--muted);
            font-size: 12px;
            margin-top: 2px;
        }

        .top-actions {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 8px;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, .72);
            color: var(--muted);
            border-radius: 999px;
            padding: 7px 12px;
            font-size: 12px;
            font-weight: 650;
        }

        .live-dot {
            width: 8px;
            height: 8px;
            border-radius: 999px;
            background: var(--mint);
            box-shadow: 0 0 0 5px rgba(32, 180, 134, .12);
        }

        .panel {
            border-radius: 22px;
            padding: 16px;
        }

        .panel-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
        }

        .panel-title b {
            font-size: 15px;
        }

        .panel-title span,
        .muted {
            color: var(--muted);
            font-size: 12px;
        }

        .sample-card {
            border-radius: 18px;
            box-shadow: none;
            padding: 13px;
            margin-bottom: 10px;
            background: rgba(248, 250, 252, .9);
        }

        .sample-card strong {
            display: block;
            margin-bottom: 5px;
            font-size: 14px;
        }

        .sample-card span {
            color: var(--muted);
            font-size: 12px;
            line-height: 1.48;
        }

        .composer {
            border-radius: 26px;
            padding: 0;
            margin-bottom: 0;
        }

        .composer h2 {
            margin: 0 0 2px;
            font-size: 24px;
            letter-spacing: 0;
        }

        .composer-caption {
            color: var(--muted);
            font-size: 12px;
            margin-bottom: 8px;
        }

        .stage-list {
            display: grid;
            gap: 7px;
        }

        .stage-row {
            display: grid;
            grid-template-columns: 28px 1fr;
            gap: 9px;
            align-items: center;
            padding: 8px;
            border-radius: 14px;
            background: rgba(255, 255, 255, .5);
            border: 1px solid transparent;
        }

        .stage-dot {
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            border: 1px solid var(--line);
            color: var(--muted);
            font-size: 11px;
            font-weight: 800;
            background: #fff;
        }

        .stage-row.active {
            background: rgba(37, 99, 235, .1);
            border-color: rgba(37, 99, 235, .25);
        }

        .stage-row.active .stage-dot {
            background: var(--blue);
            border-color: var(--blue);
            color: #fff;
        }

        .stage-row.done .stage-dot {
            background: rgba(32, 180, 134, .13);
            border-color: rgba(32, 180, 134, .22);
            color: #08765b;
        }

        .stage-row b {
            display: block;
            font-size: 12px;
        }

        .stage-row small {
            color: var(--muted);
            display: block;
            font-size: 10px;
            margin-top: 2px;
        }

        .phase-tag {
            display: inline-block;
            margin-top: 10px;
            color: #0f766e;
            background: rgba(32, 180, 134, .12);
            border-radius: 999px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 750;
        }

        .metric-strip {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin: 10px 0 14px;
        }

        .metric-card {
            border-radius: 16px;
            box-shadow: none;
            padding: 13px 14px;
            background: rgba(255, 255, 255, .75);
        }

        .metric-card span {
            color: var(--muted);
            display: block;
            font-size: 12px;
        }

        .metric-card b {
            display: block;
            font-size: 20px;
            margin-top: 4px;
        }

        .summary-box {
            min-height: 0;
        }

        .summary-empty {
            min-height: 74px;
            display: grid;
            place-items: center;
            text-align: center;
            color: var(--muted);
            border: 1px dashed var(--line);
            border-radius: 18px;
            background: rgba(255, 255, 255, .42);
            padding: 12px;
            font-size: 12px;
        }

        .brief-line {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            border-bottom: 1px solid var(--line);
            padding: 8px 0;
            font-size: 12px;
        }

        .brief-line span {
            color: var(--muted);
        }

        .report-page {
            max-width: 1040px;
            max-height: calc(100vh - 1.2rem);
            overflow: auto;
            margin: 0 auto;
            padding-bottom: 1rem;
        }

        .stButton > button {
            border-radius: 999px;
            min-height: 36px;
            font-weight: 750;
            border: 1px solid var(--line);
            box-shadow: none;
        }

        .stButton > button[kind="primary"] {
            background: #172033;
            border-color: #172033;
            color: #fff;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            border-radius: 16px;
            border-color: var(--line);
            background: rgba(255, 255, 255, .88);
        }

        div[data-testid="stTextInput"],
        div[data-testid="stTextArea"],
        div[data-testid="stMultiSelect"],
        div[data-testid="stSelectbox"] {
            margin-bottom: .2rem;
        }

        div[data-testid="stMultiSelect"] div,
        div[data-testid="stSelectbox"] div {
            border-radius: 16px;
        }

        [data-testid="stTabs"] button {
            font-weight: 750;
        }

        [data-testid="stProgress"] {
            padding-top: 2px;
            padding-bottom: 8px;
        }

        [data-testid="stProgress"] div {
            overflow: visible !important;
        }

        [data-testid="stProgress"] p {
            line-height: 1.55;
            min-height: 28px;
            margin-bottom: 4px;
            overflow: visible !important;
        }

        [data-testid="stAlert"] {
            padding-top: 10px;
            padding-bottom: 10px;
        }

        [data-testid="stAlert"] p {
            line-height: 1.45;
            overflow: visible;
        }

        @media (max-width: 1100px) {
            .metric-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 760px) {
            .demo-topbar {
                align-items: flex-start;
                flex-direction: column;
                padding: 14px;
            }

            .metric-strip {
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
    dimensions = []
    seen_dimensions = set()
    selected_indicators = st.session_state.get("selected_indicators", [])
    custom_indicators = parse_list(st.session_state.custom_indicators)
    shared_indicators = list(dict.fromkeys(selected_indicators + custom_indicators))
    selected_dimensions = st.session_state.get("selected_dimensions", [])
    all_dimensions = selected_dimensions + parse_list(st.session_state.custom_dimensions)
    for dimension in all_dimensions:
        if dimension in seen_dimensions:
            continue
        seen_dimensions.add(dimension)
        preset_indicators = DIMENSION_PRESETS.get(dimension, [])[:2]
        indicators = list(dict.fromkeys(preset_indicators + shared_indicators))
        if not indicators:
            indicators = ["核心能力", "用户体验", "市场表现"]
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
    for index, (key, title, caption, detail) in enumerate(STAGES, 1):
        state = "active" if key == active_stage else "done" if key in done else ""
        mark = "✓" if key in done else str(index)
        html.append(
            f'<div class="stage-row {state}"><div class="stage-dot">{mark}</div>'
            f"<div><b>{escape(title)} · {escape(caption)}</b>"
            f"<small>{escape(detail)}</small></div></div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_metric(label: str, value: str) -> str:
    return f"<div class='metric-card'><span>{escape(label)}</span><b>{escape(value)}</b></div>"


def initialize_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    if "dimensions_input" in st.session_state and "selected_dimensions" not in st.session_state:
        entered_dimensions = parse_list(st.session_state.dimensions_input)
        st.session_state.selected_dimensions = [
            dimension for dimension in entered_dimensions if dimension in DIMENSION_PRESETS
        ]
        st.session_state.custom_dimensions = ", ".join(
            dimension for dimension in entered_dimensions if dimension not in DIMENSION_PRESETS
        )
    if "dimensions" in st.session_state and "selected_dimensions" not in st.session_state:
        st.session_state.selected_dimensions = [
            dimension for dimension in st.session_state.dimensions if dimension in DIMENSION_PRESETS
        ]
    st.session_state.setdefault("latest_result", None)
    st.session_state.setdefault("latest_brief", None)


def render_topbar() -> None:
    st.markdown(
        """
        <div class="demo-topbar">
          <div class="brand">
            <div class="brand-mark">CE</div>
            <div>
              <div class="brand-title">CompEye Agent</div>
              <div class="brand-subtitle">Evidence-first multi-agent competitor analysis demo</div>
            </div>
          </div>
          <div class="top-actions">
            <span class="pill"><span class="live-dot"></span> Live Demo</span>
            <span class="pill">MiMo V2.5 / Pro</span>
            <span class="pill">CrewAI Phase 1</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def report_view_requested() -> bool:
    return st.query_params.get("view") == "report"


def render_report_button(key: str) -> None:
    if st.button("查看完整报告", key=key, use_container_width=True):
        st.query_params["view"] = "report"
        st.rerun()


def render_report_page() -> None:
    st.markdown('<main class="report-page">', unsafe_allow_html=True)
    if st.button("返回工作台", use_container_width=False):
        st.query_params.clear()
        st.rerun()

    st.markdown('<section class="panel">', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-title"><b>完整竞品分析报告</b><span>Report Detail</span></div>',
        unsafe_allow_html=True,
    )
    result = st.session_state.get("latest_result")
    brief = st.session_state.get("latest_brief")
    if result is None:
        st.info("当前还没有生成报告。请返回工作台先运行一次分析。")
    else:
        report_tab, verify_tab, brief_tab = st.tabs(["完整报告", "Verifier JSON", "Input Brief"])
        with report_tab:
            st.markdown(result.report)
        with verify_tab:
            st.code(result.verifier_result, language="json")
        with brief_tab:
            st.json(brief or {})
    st.markdown("</section></main>", unsafe_allow_html=True)


def render_summary_placeholder() -> None:
    st.markdown(
        """
        <div class="summary-empty">
          <div>
            <b>报告总结会显示在这里</b><br>
            运行分析后，这里只展示验证状态、重写状态、报告长度和简短预览。完整报告通过按钮进入新页面查看。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_brief_summary(inputs: dict) -> None:
    dimensions = "、".join(item["name"] for item in inputs["dimensions"]) or "-"
    competitors = "、".join(inputs["competitors"]) or "-"
    st.markdown(
        f"""
        <div class="brief-line"><span>目标产品</span><b>{escape(inputs["productName"] or "-")}</b></div>
        <div class="brief-line"><span>竞品</span><b>{escape(competitors)}</b></div>
        <div class="brief-line"><span>维度</span><b>{escape(dimensions)}</b></div>
        <div class="brief-line"><span>输出形式</span><b>{escape(inputs["analysisType"])}</b></div>
        """,
        unsafe_allow_html=True,
    )


initialize_state()
inject_styles()
if report_view_requested():
    render_report_page()
    st.stop()

left_col, center_col, right_col = st.columns([1.1, 1.35, 1.05], gap="medium")

with left_col:
    with st.container(border=True, height=WORKSPACE_PANEL_HEIGHT):
        st.markdown("## 配置分析")
        st.caption("填写任意目标产品、竞品和分析维度。")
        run_button = st.button("开始分析", type="primary", use_container_width=True)

        st.text_input("目标产品", key="product_name", placeholder="输入要分析的产品或品牌")
        st.text_input("竞品", key="competitors", help="用逗号分隔多个竞品。", placeholder="竞品 A, 竞品 B")
        st.multiselect(
            "分析维度",
            options=list(DIMENSION_PRESETS.keys()),
            key="selected_dimensions",
            help="选择常用维度，也可以直接输入新维度并回车添加。",
            placeholder="选择或输入分析维度",
            accept_new_options=True,
        )
        st.multiselect(
            "重点指标",
            options=INDICATOR_OPTIONS,
            key="selected_indicators",
            help="选择常用指标，也可以直接输入新指标并回车添加。",
            placeholder="选择或输入重点指标",
            accept_new_options=True,
        )
        st.selectbox("输出形式", ["SWOT", "对比表格", "综合报告"], key="analysis_type")

with center_col:
    with st.container(border=True, height=WORKSPACE_PANEL_HEIGHT):
        st.markdown("### 报告总结")
        st.caption("完整报告通过按钮进入独立页面查看。")
        result_container = st.container()
        with result_container:
            latest_result = st.session_state.get("latest_result")
            latest_brief = st.session_state.get("latest_brief")
            if latest_result is None:
                st.markdown("**当前 Brief**")
                render_brief_summary(build_inputs())
                render_summary_placeholder()
            else:
                status_text = "Passed" if latest_result.passed else "Needs review"
                retry_text = "Yes" if latest_result.retried else "No"
                report_size = f"{len(latest_result.report)} chars"
                st.markdown(
                    "<div class='metric-strip'>"
                    + render_metric("Verifier", status_text)
                    + render_metric("Rewrite", retry_text)
                    + render_metric("Report", report_size)
                    + render_metric("Output", (latest_brief or {}).get("analysisType", "-"))
                    + "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("**报告预览**")
                with st.container(height=360):
                    st.markdown(latest_result.report[:1600] + ("..." if len(latest_result.report) > 1600 else ""))
                render_report_button("open_report_from_summary")

with right_col:
    with st.container(border=True, height=WORKSPACE_PANEL_HEIGHT):
        st.markdown("### Agent 执行追踪")
        quick_mode = st.toggle("快速演示模式", value=True, help="关闭后启用失败自动重写一次。")
        show_brief = st.toggle("显示结构化 brief", value=False)
        stage_slot = st.empty()
        status_slot = st.empty()
        progress_slot = st.empty()
        with stage_slot:
            if st.session_state.get("latest_result") is None:
                render_stage_board()
            else:
                render_stage_board(done={key for key, _, _, _ in STAGES})
        if st.session_state.get("latest_result") is not None:
            status_slot.success("Run complete")
            progress_slot.progress(1.0, text="Run complete")
        if show_brief:
            st.markdown("**Brief JSON**")
            st.json(build_inputs(), expanded=False)

if run_button:
    try:
        validated = CompetitorInput(**build_inputs()).model_dump()
    except Exception as exc:
        st.error(f"输入不完整或不合法：{exc}")
        st.stop()

    stage_order = {key: idx for idx, (key, _, _, _) in enumerate(STAGES)}
    done_stages: set[str] = set()

    def update_progress(stage: str, message: str) -> None:
        for key, _, _, _ in STAGES:
            if stage_order[key] < stage_order.get(stage, 0):
                done_stages.add(key)
        with stage_slot:
            render_stage_board(active_stage=stage, done=done_stages)
        status_slot.info(message)
        progress_slot.progress(
            min((stage_order.get(stage, 0) + 1) / len(STAGES), 0.96),
            text=message,
        )
        time.sleep(0.12)

    with result_container:
        with st.spinner("Agent crew is working..."):
            update_progress("collect", "Collector 正在采集公开证据")
            result = run_analysis(
                validated,
                allow_retry=not quick_mode,
                progress_callback=update_progress,
            )

        with stage_slot:
            render_stage_board(done={key for key, _, _, _ in STAGES})
        status_slot.success("Run complete")
        progress_slot.progress(1.0, text="Run complete")
        st.session_state.latest_result = result
        st.session_state.latest_brief = validated
        st.rerun()
