import json
import re
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from crew import analysis_crew
from crewai import Crew
from crew.agents.verifier import verifier
from crew.agents.writer import writer
from tasks.verify_task import verify_task
from tasks.write_task import write_task


SOURCE_MARKERS = ("[来源:", "source_references", "provenance", "来源 URL", "来源:")
SOURCE_BLOCK_MARKERS = ("Provenance 索引", "provenance 索引", "来源索引", "参考来源")
DEFAULT_EVIDENCE_INDEX = "Evidence Index: no indexed evidence is available for this request."


@dataclass
class AnalysisRunResult:
    report: str
    verifier_result: str
    passed: bool
    retried: bool = False


ProgressCallback = Callable[[str, str], None]


def run_analysis(
    inputs: dict[str, Any],
    allow_retry: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> AnalysisRunResult:
    """Run the Phase 1 chain, verify provenance, and rewrite once if needed."""
    inputs = _with_default_evidence_index(inputs)
    _emit_progress(progress_callback, "collect", "Collector 正在采集公开信息")
    kickoff_result = analysis_crew.kickoff(inputs=inputs)
    _emit_progress(progress_callback, "verify", "Verifier 正在检查报告证据")
    report = _task_output(write_task, fallback=kickoff_result)
    verifier_result = _task_output(verify_task, fallback=kickoff_result)
    issues = _verification_issues(report, verifier_result)

    if not issues or not allow_retry:
        return AnalysisRunResult(
            report=report,
            verifier_result=verifier_result,
            passed=not issues,
        )

    _emit_progress(progress_callback, "rewrite", "首次质检未通过，正在重写报告")
    retry_result, retry_write_task, retry_verify_task = _rewrite_and_verify(inputs, issues)
    _emit_progress(progress_callback, "final", "正在整理最终结果")
    retry_report = _task_output(retry_write_task, fallback=retry_result)
    retry_verifier = _task_output(retry_verify_task, fallback=retry_result)
    retry_issues = _verification_issues(retry_report, retry_verifier)

    return AnalysisRunResult(
        report=retry_report,
        verifier_result=retry_verifier,
        passed=not retry_issues,
        retried=True,
    )


def _rewrite_and_verify(inputs: dict[str, Any], issues: list[str]) -> tuple[Any, Any, Any]:
    retry_issues = "\n".join(f"- {issue}" for issue in issues)
    retry_write_task = write_task.__class__(
        description=(
            f"{write_task.description}\n\n"
            "上一次质检未通过，请只重写报告并修复以下问题：\n"
            f"{retry_issues}\n"
            "必须保留每条结论后的来源标注，并在末尾输出 provenance 索引。"
        ),
        agent=writer,
        expected_output=write_task.expected_output,
        context=write_task.context,
    )
    retry_verify_task = verify_task.__class__(
        description=verify_task.description,
        agent=verifier,
        expected_output=verify_task.expected_output,
        context=[retry_write_task],
    )

    retry_crew = Crew(
        agents=[writer, verifier],
        tasks=[retry_write_task, retry_verify_task],
        flow="sequential",
        verbose=True,
    )
    result = retry_crew.kickoff(inputs=inputs)
    return result, retry_write_task, retry_verify_task


def _verification_issues(report: str, verifier_result: str) -> list[str]:
    issues: list[str] = []

    issues.extend(_provenance_guard(report))

    verdict = _parse_verifier_result(verifier_result)
    if verdict:
        passed = verdict.get("passed")
        confidence = verdict.get("confidence")
        if passed is False:
            issues.append("Verifier 判定未通过")
        if isinstance(confidence, (int, float)) and confidence < 60:
            issues.append(f"Verifier 置信度低于阈值: {confidence}")
        for item in verdict.get("issues", []) or []:
            if isinstance(item, dict):
                description = item.get("description") or item.get("type")
                if description:
                    issues.append(str(description))

    return issues


def _provenance_guard(report: str) -> list[str]:
    issues: list[str] = []
    urls = re.findall(r"https?://[^\s\])>，。；,]+", report)

    if not any(marker in report for marker in SOURCE_BLOCK_MARKERS):
        issues.append("最终报告缺少 provenance / 来源索引区块")

    if not urls:
        issues.append("最终报告缺少可访问 URL")

    source_tag_count = len(re.findall(r"\[来源:\s*[^\]]+\]", report))
    claim_like_lines = _claim_like_lines(report)
    if claim_like_lines and source_tag_count < len(claim_like_lines):
        issues.append(
            f"来源标注不足：检测到 {len(claim_like_lines)} 条结论式条目，但只有 {source_tag_count} 个 [来源: ...] 标注"
        )

    if "待核实" in report and source_tag_count == 0:
        issues.append("报告包含待核实内容，但没有提供来源标注或复核入口")

    return issues


def _claim_like_lines(report: str) -> list[str]:
    lines: list[str] = []
    for raw_line in report.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^#{1,6}\s+", line) or "|" in line:
            continue
        if re.match(r"^([-*]|\d+[.)])\s+", line) and len(line) >= 18:
            lines.append(line)
    return lines


def _parse_verifier_result(verifier_result: str) -> dict[str, Any] | None:
    text = verifier_result.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _task_output(task: Any, fallback: Any) -> str:
    output = getattr(task, "output", None)
    if output is not None:
        raw = getattr(output, "raw", None)
        if raw:
            return str(raw)
        return str(output)
    return str(fallback)


def _emit_progress(callback: ProgressCallback | None, stage: str, message: str) -> None:
    if callback:
        callback(stage, message)


def _with_default_evidence_index(inputs: dict[str, Any]) -> dict[str, Any]:
    next_inputs = dict(inputs)
    next_inputs.setdefault("evidenceIndex", DEFAULT_EVIDENCE_INDEX)
    return next_inputs
