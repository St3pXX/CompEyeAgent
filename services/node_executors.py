"""Per-node executors for the DAG scheduler.

Each executor creates a single-node CrewAI Crew, reads upstream context from
the Scratchpad, and writes its output back. This replaces the legacy monolithic
chain that ran all four stages inside the ``collect`` node.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from models.coordinator import DAGNode, NodeExecutionResult
from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from services.telemetry import trace_llm_call
from services.verification import verification_issues, parse_verifier_result

# Maximum characters to inject from upstream scratchpad content into a task
# description. Prevents context window overflow for large raw data.
_UPSTREAM_TRUNCATE = 6000

DEFAULT_EVIDENCE_INDEX = "Evidence Index: no indexed evidence is available for this request."


def _read_scratchpad(foundation: CoordinatorFoundationService, run_id: str, path: str) -> str:
    """Read a scratchpad item by path, returning empty string if missing."""
    try:
        item = foundation.store.get_scratchpad_item(run_id, path)
        return item.content
    except Exception:
        return ""


def _truncate(text: str, max_chars: int = _UPSTREAM_TRUNCATE) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... 内容已截断，完整数据见 Scratchpad ...]"


def _count_evidence_items(raw_output: str) -> int:
    """Best-effort count of evidence items in collect output (JSON array)."""
    import json

    try:
        data = json.loads(raw_output)
        if isinstance(data, list):
            return len(data)
    except Exception:
        pass
    return 0


def _parse_verifier_verdict(raw_output: str) -> str:
    """Extract a short human-readable verdict from verifier JSON output."""
    import json

    try:
        data = json.loads(raw_output)
        passed = data.get("passed")
        confidence = data.get("confidence")
        issues = data.get("issues") or []
        parts: list[str] = []
        if isinstance(passed, bool):
            parts.append("通过" if passed else "未通过")
        if isinstance(confidence, (int, float)):
            parts.append(f"置信度 {confidence}")
        if issues:
            parts.append(f"{len(issues)} 个问题")
        if parts:
            return "、".join(parts)
    except Exception:
        pass
    return "结果已生成"


def _run_single_crew(agent: Any, task: Any, inputs: dict[str, Any], node_key: str = "unknown") -> str:
    """Create a single-agent single-task Crew and return the raw output."""
    from crewai import Crew

    crew = Crew(
        agents=[agent],
        tasks=[task],
        flow="sequential",
        verbose=True,
    )
    prompt_length = len(task.description) if hasattr(task, "description") else None
    with trace_llm_call(node_key, node_key, prompt_length=prompt_length):
        result = crew.kickoff(inputs=inputs)
    output = getattr(task, "output", None)
    if output is not None:
        raw = getattr(output, "raw", None)
        if raw:
            return str(raw)
    return str(result)


# ---------------------------------------------------------------------------
# Individual node executors
# ---------------------------------------------------------------------------

def _execute_collect(
    *,
    run_id: str,
    node: DAGNode,
    context: dict[str, Any],
    progress_callback: Callable[[str, str], None],
    foundation: CoordinatorFoundationService,
) -> NodeExecutionResult:
    """Collect: gather public info via web search."""
    from crewai import Task
    from crew.agents.collector import collector

    input_data: CompetitorInput = context["input_data"]
    inputs = input_data.model_dump()
    inputs.setdefault("evidenceIndex", context.get("evidence_index", DEFAULT_EVIDENCE_INDEX))

    competitors_desc = "、".join(input_data.competitors) or "未指定"
    progress_callback("collect", f"Collector 启动：检索 Evidence Index 中关于 {competitors_desc} 的已有证据")
    progress_callback("collect", "Evidence Index 检查完成，证据不足的部分将通过联网搜索补充")

    task = Task(
        description=(
            "根据用户提供的竞品列表和维度，使用网络搜索工具采集每个竞品的公开信息。\n"
            "用户输入：\n"
            "- 目标产品：{productName}\n"
            "- 竞品列表：{competitors}\n"
            "- 分析维度：{dimensions}\n"
            "- 分析类型：{analysisType}\n\n"
            "可用的 Evidence Index：\n"
            "{evidenceIndex}\n"
            "优先使用 Evidence Index 中已有的结构化证据；证据不足时再使用网络搜索补充。\n"
            "使用 Evidence Index 时必须保留其中的 source URL、snippet、confidence 和 provider。\n\n"
            "信息来源允许稀疏覆盖：不要求每类来源都查到信息。\n"
            "如果某个结论已经能被其他可信来源支撑，可以综合采用；只有结论本身缺少可核验证据时才标记为“待核实”。\n\n"
            "执行步骤：\n"
            "1. 先检查 Evidence Index 中是否已有匹配竞品和维度的证据\n"
            "2. Evidence Index 证据不足时，对每个竞品使用网络搜索\n"
            "3. 跨来源综合时按来源可信度和原文相关性判断\n"
            "4. 每条数据必须记录来源 URL 和关键原文片段\n"
            "5. 以结构化 JSON 格式输出每条采集结果\n\n"
            "输出格式必须是 JSON 数组，数组项遵循 Evidence Schema：\n"
            '{"competitor": "竞品名", "dimension": "维度名", "indicator": "指标名", '
            '"summary": "采集摘要", "source_references": [{"uri": "https://...", "snippet": "原文片段"}]}\n'
            "禁止输出没有 source_references 的采集项。"
        ),
        agent=collector,
        expected_output="结构化 Evidence JSON 数组，每条数据附有 provenance",
    )

    output = _run_single_crew(collector, task, inputs, node_key="collect")
    evidence_count = _count_evidence_items(output)
    progress_callback("collect", f"采集完成，共获取 {evidence_count} 条证据，已写入 Scratchpad")
    return NodeExecutionResult(
        output_refs=["collect/raw.json"],
        scratchpad_outputs={"collect/raw.json": output},
    )


def _execute_analyze(
    *,
    run_id: str,
    node: DAGNode,
    context: dict[str, Any],
    progress_callback: Callable[[str, str], None],
    foundation: CoordinatorFoundationService,
) -> NodeExecutionResult:
    """Analyze: structured SWOT/comparison analysis."""
    from crewai import Task
    from crew.agents.analyzer import analyzer

    progress_callback("analyze", "Analyzer 启动：读取 Collector 采集的原始数据")

    raw_data = _read_scratchpad(foundation, run_id, "collect/raw.json")
    if not raw_data:
        raise RuntimeError("collect/raw.json 不存在于 Scratchpad 中，无法执行分析")

    truncated = _truncate(raw_data)
    analysis_type = context["input_data"].analysisType if "input_data" in context else "SWOT"
    progress_callback("analyze", f"数据加载完成，正在生成 {analysis_type} 结构化结论（每条附 provenance）")

    task = Task(
        description=(
            "读取采集的原始数据，执行结构化分析（SWOT 或对比表格）。\n\n"
            f"以下是 Collector 采集的原始数据：\n\n{truncated}\n\n"
            "执行步骤：\n"
            "1. 分析每个竞品在各维度上的表现\n"
            "2. 生成结构化分析结论（Strengths/Weaknesses/Opportunities/Threats）\n"
            "3. 每条分析结论必须附带 provenance（指向原始数据来源）\n\n"
            "输出：结构化分析结论 JSON，每条结论附有 provenance。"
        ),
        agent=analyzer,
        expected_output="结构化分析结论 JSON（SWOT 格式），每条结论附有 provenance",
    )

    output = _run_single_crew(analyzer, task, {}, node_key="analyze")
    progress_callback("analyze", "结构化分析完成，结论已写入 Scratchpad")
    return NodeExecutionResult(
        output_refs=["analyze/findings.json"],
        scratchpad_outputs={"analyze/findings.json": output},
    )


def _execute_write(
    *,
    run_id: str,
    node: DAGNode,
    context: dict[str, Any],
    progress_callback: Callable[[str, str], None],
    foundation: CoordinatorFoundationService,
) -> NodeExecutionResult:
    """Write: generate Markdown report with provenance."""
    from crewai import Task
    from crew.agents.writer import writer

    progress_callback("write", "Writer 启动：读取 Analyzer 的结构化结论")

    findings = _read_scratchpad(foundation, run_id, "analyze/findings.json")
    if not findings:
        raise RuntimeError("analyze/findings.json 不存在于 Scratchpad 中，无法撰写报告")

    truncated = _truncate(findings)
    progress_callback("write", "正在撰写 Markdown 报告，每条结论附 [来源: URL] 标注和 Provenance 索引")

    task = Task(
        description=(
            "将分析结论组织为可读的 Markdown 竞品分析报告。\n\n"
            f"以下是 Analyzer 的结构化分析结论：\n\n{truncated}\n\n"
            "执行步骤：\n"
            "1. 按照报告规范组织内容（SWOT 框架或对比表格）\n"
            "2. 每个分析结论必须在同一条 bullet 内附带来源标注，格式严格为 [来源: https://...]\n"
            "3. 在报告末尾附上标题为“Provenance 索引”的来源索引表\n"
            "4. 没有来源支撑的结论必须删除或标记为“待核实”\n\n"
            "输出：Markdown 格式竞品分析报告，每条结论有来源标注。"
        ),
        agent=writer,
        expected_output="Markdown 格式竞品分析报告，包含 SWOT 或对比表格，每条结论附有来源标注",
    )

    output = _run_single_crew(writer, task, {}, node_key="write")
    progress_callback("write", "报告撰写完成，已写入 Scratchpad")
    return NodeExecutionResult(
        output_refs=["write/report.md"],
        scratchpad_outputs={"write/report.md": output},
    )


def _execute_verify(
    *,
    run_id: str,
    node: DAGNode,
    context: dict[str, Any],
    progress_callback: Callable[[str, str], None],
    foundation: CoordinatorFoundationService,
) -> NodeExecutionResult:
    """Verify: independent quality check on the report."""
    from crewai import Task
    from crew.agents.verifier import verifier

    progress_callback("verify", "Verifier 启动：独立校验报告草稿（不继承撰写者上下文）")

    report = _read_scratchpad(foundation, run_id, "write/report.md")
    if not report:
        raise RuntimeError("write/report.md 不存在于 Scratchpad 中，无法执行质检")

    truncated = _truncate(report)
    progress_callback("verify", "正在检测逻辑矛盾、幻觉和缺失来源")

    task = Task(
        description=(
            "独立校验报告草稿的准确性，主动寻找问题。\n\n"
            f"以下是 Writer 生成的报告草稿：\n\n{truncated}\n\n"
            "检查项：\n"
            "1. 逻辑矛盾检测（同一竞品不同维度结论是否一致）\n"
            "2. 数据一致性验证（报告数据与原始采集数据是否匹配）\n"
            "3. 幻觉检测（结论是否有对应的证据支持）\n"
            "4. 缺失关键维度检测（是否有关键维度未覆盖）\n\n"
            "质检策略：\n"
            "- confidence >= 90：报告通过\n"
            "- 60 <= confidence < 90：标记待复核\n"
            "- confidence < 60：不通过\n\n"
            "输出：质检结果 JSON {passed, confidence, issues: [{type, description}]}。"
        ),
        agent=verifier,
        expected_output="质检结果 JSON：{passed: bool, confidence: 0-100, issues: [{type, description}]}",
    )

    output = _run_single_crew(verifier, task, {}, node_key="verify")
    verdict = _parse_verifier_verdict(output)
    progress_callback("verify", f"质检完成：{verdict}")
    return NodeExecutionResult(
        output_refs=["verify/verifier.json"],
        scratchpad_outputs={"verify/verifier.json": output},
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_NODE_EXECUTORS: dict[str, Callable[..., NodeExecutionResult]] = {
    "collect": _execute_collect,
    "analyze": _execute_analyze,
    "write": _execute_write,
    "verify": _execute_verify,
}


def per_node_executor(
    *,
    run_id: str,
    node: DAGNode,
    context: dict[str, Any],
    progress_callback: Callable[[str, str], None],
    foundation: CoordinatorFoundationService,
    **_kwargs: Any,
) -> NodeExecutionResult:
    """Dispatch to the appropriate per-node executor based on node.key."""
    executor = _NODE_EXECUTORS.get(node.key)
    if executor is None:
        raise RuntimeError(f"未知的 DAG 节点类型：{node.key}")
    return executor(
        run_id=run_id,
        node=node,
        context=context,
        progress_callback=progress_callback,
        foundation=foundation,
    )
