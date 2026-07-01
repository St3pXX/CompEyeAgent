"""Graph node functions for the CompEye analysis pipeline.

Each node is a pure-ish function ``(state) -> state_update``.  It calls the
litellm-backed ``LLMClient`` directly (no CrewAI), reads upstream output from
the state, and returns the fields it produced.  Store/event_bus wiring is
layered on in the runner (module 3); these nodes stay framework-light and
testable.

The token-accounting run_id is re-set at each node entry because LangGraph may
execute nodes on different threads/tasks, and ``llm_telemetry`` keys tokens by a
contextvar run_id.
"""

from __future__ import annotations

import json
from typing import Any

from config.settings import (
    ANALYZER_MODEL,
    COLLECTOR_MODEL,
    VERIFIER_MODEL,
    WRITER_MODEL,
    create_llm_client,
)
from graph import prompts
from graph.state import AnalysisState
from services import llm_telemetry
from services.verification import verification_issues
from services.web_search import web_search

# Maximum characters of upstream scratchpad content injected into a prompt.
_UPSTREAM_TRUNCATE = 6000

DEFAULT_EVIDENCE_INDEX = "Evidence Index: no indexed evidence is available for this request."


def _truncate(text: str, max_chars: int = _UPSTREAM_TRUNCATE) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... 内容已截断，完整数据见 Scratchpad ...]"


def _count_evidence_items(raw_output: str) -> int:
    """Best-effort count of evidence items in collect output (JSON array)."""
    try:
        data = json.loads(raw_output)
        if isinstance(data, list):
            return len(data)
    except Exception:
        pass
    return 0


def _parse_verifier_verdict(raw_output: str) -> str:
    """Extract a short human-readable verdict from verifier JSON output."""
    try:
        data = json.loads(raw_output)
        passed = data.get("passed")
        confidence = data.get("confidence")
        if passed is True:
            return f"通过（confidence={confidence}）"
        if passed is False:
            return f"未通过（confidence={confidence}）"
    except Exception:
        pass
    return "已完成"


def _emit(state: AnalysisState, stage: str, message: str) -> None:
    cb = state.get("_progress")
    if cb is not None:
        cb(stage, message)


def _set_run_id(state: AnalysisState) -> None:
    run_id = state.get("run_id")
    if run_id:
        llm_telemetry.set_current_run_id(run_id)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def collect_node(state: AnalysisState) -> dict[str, Any]:
    """Collect public info via web search + LLM structuring."""
    _set_run_id(state)

    input_data = state["input_data"]
    evidence_index = state.get("evidence_index") or DEFAULT_EVIDENCE_INDEX
    competitors = "、".join(input_data.competitors) or "未指定"
    dimensions = "、".join(d.name for d in input_data.dimensions) or "未指定"

    _emit(state, "collect", f"Collector 启动：检索 Evidence Index 中关于 {competitors} 的已有证据")
    _emit(state, "collect", "Evidence Index 检查完成，证据不足的部分将通过联网搜索补充")

    # Web search to gather raw context, then structure it via the LLM.
    search_result = web_search(prompts.collect_web_search_prompt(
        product_name=input_data.productName,
        competitors=competitors,
        dimensions=dimensions,
    ))

    prompt = prompts.collect_prompt(
        product_name=input_data.productName,
        competitors=competitors,
        dimensions=dimensions,
        analysis_type=input_data.analysisType,
        evidence_index=f"{evidence_index}\n\n联网搜索补充结果：\n{_truncate(search_result)}",
    )
    client = create_llm_client(COLLECTOR_MODEL)
    output = client(prompt, system=prompts.COLLECTOR_SYSTEM).text

    _emit(state, "collect", f"采集完成，共获取 {_count_evidence_items(output)} 条证据，已写入 Scratchpad")
    return {"collect_raw": output}


def analyze_node(state: AnalysisState) -> dict[str, Any]:
    """Structured SWOT/comparison analysis of collected data."""
    _set_run_id(state)
    raw = state.get("collect_raw", "")
    if not raw:
        raise RuntimeError("collect_raw 缺失，无法执行分析")

    analysis_type = state["input_data"].analysisType
    _emit(state, "analyze", "Analyzer 启动：读取 Collector 采集的原始数据")
    _emit(state, "analyze", f"数据加载完成，正在生成 {analysis_type} 结构化结论（每条附 provenance）")

    prompt = prompts.analyze_prompt(raw_data=_truncate(raw))
    client = create_llm_client(ANALYZER_MODEL)
    output = client(prompt, system=prompts.ANALYZER_SYSTEM).text

    _emit(state, "analyze", "结构化分析完成，结论已写入 Scratchpad")
    return {"analyze_findings": output}


def write_node(state: AnalysisState) -> dict[str, Any]:
    """Generate the Markdown report with provenance annotations."""
    _set_run_id(state)
    findings = state.get("analyze_findings", "")
    if not findings:
        raise RuntimeError("analyze_findings 缺失，无法撰写报告")

    _emit(state, "write", "Writer 启动：读取 Analyzer 的结构化结论")
    _emit(state, "write", "正在撰写 Markdown 报告，每条结论附 [来源: URL] 标注和 Provenance 索引")

    prompt = prompts.write_prompt(findings=_truncate(findings))
    client = create_llm_client(WRITER_MODEL)
    output = client(prompt, system=prompts.WRITER_SYSTEM).text

    _emit(state, "write", "报告撰写完成，已写入 Scratchpad")
    return {"report": output}


def verify_node(state: AnalysisState) -> dict[str, Any]:
    """Independent quality check on the report; compute provenance issues."""
    _set_run_id(state)
    report = state.get("report", "")
    if not report:
        raise RuntimeError("report 缺失，无法执行质检")

    _emit(state, "verify", "Verifier 启动：独立校验报告草稿（不继承撰写者上下文）")
    _emit(state, "verify", "正在检测逻辑矛盾、幻觉和缺失来源")

    prompt = prompts.verify_prompt(report=_truncate(report))
    client = create_llm_client(VERIFIER_MODEL)
    verifier_result = client(prompt, system=prompts.VERIFIER_SYSTEM).text

    _emit(state, "verify", f"质检完成：{_parse_verifier_verdict(verifier_result)}")

    issues = verification_issues(report, verifier_result)
    return {
        "verifier_result": verifier_result,
        "issues": issues,
        "passed": not issues,
    }


def rewrite_node(state: AnalysisState) -> dict[str, Any]:
    """Rewrite the report once, injecting prior verification issues."""
    _set_run_id(state)
    findings = state.get("analyze_findings", "")
    issues = state.get("issues", [])
    issues_text = "\n".join(f"- {issue}" for issue in issues)

    _emit(state, "rewrite", "首次质检未通过，正在重写报告")

    prompt = prompts.rewrite_prompt(findings=_truncate(findings), issues=issues_text)
    client = create_llm_client(WRITER_MODEL)
    output = client(prompt, system=prompts.WRITER_SYSTEM).text

    return {
        "report": output,
        "retry_count": state.get("retry_count", 0) + 1,
        "retried": True,
    }
