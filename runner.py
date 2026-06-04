import json
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

from crew import analysis_crew
from crewai import Crew
from crew.agents.verifier import verifier
from crew.agents.writer import writer
from services.verification import (
    SOURCE_MARKERS,
    SOURCE_BLOCK_MARKERS,
    verification_issues,
    provenance_guard,
    claim_like_lines,
    parse_verifier_result,
)
from tasks.analyze_task import analyze_task
from tasks.collect_task import collect_info_task
from tasks.verify_task import verify_task
from tasks.write_task import write_task


DEFAULT_EVIDENCE_INDEX = "Evidence Index: no indexed evidence is available for this request."


@dataclass
class AnalysisRunResult:
    report: str
    verifier_result: str
    passed: bool
    retried: bool = False
    scratchpad_outputs: dict[str, str] = field(default_factory=dict)


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
    scratchpad_outputs = {
        "collect/raw.json": _task_output(collect_info_task, fallback=""),
        "analyze/findings.json": _task_output(analyze_task, fallback=""),
        "write/report.md": report,
        "verify/verifier.json": verifier_result,
    }
    issues = _verification_issues(report, verifier_result)

    if not issues or not allow_retry:
        return AnalysisRunResult(
            report=report,
            verifier_result=verifier_result,
            passed=not issues,
            scratchpad_outputs=scratchpad_outputs,
        )

    _emit_progress(progress_callback, "rewrite", "首次质检未通过，正在重写报告")
    retry_result, retry_write_task, retry_verify_task = _rewrite_and_verify(inputs, issues)
    _emit_progress(progress_callback, "final", "正在整理最终结果")
    retry_report = _task_output(retry_write_task, fallback=retry_result)
    retry_verifier = _task_output(retry_verify_task, fallback=retry_result)
    scratchpad_outputs.update(
        {
            "write/report.md": retry_report,
            "verify/verifier.json": retry_verifier,
            "write/retry_report.md": retry_report,
            "verify/retry_verifier.json": retry_verifier,
        }
    )
    retry_issues = _verification_issues(retry_report, retry_verifier)

    return AnalysisRunResult(
        report=retry_report,
        verifier_result=retry_verifier,
        passed=not retry_issues,
        retried=True,
        scratchpad_outputs=scratchpad_outputs,
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
    """Delegated to services.verification.verification_issues."""
    return verification_issues(report, verifier_result)


def _provenance_guard(report: str) -> list[str]:
    """Delegated to services.verification.provenance_guard."""
    return provenance_guard(report)


def _claim_like_lines(report: str) -> list[str]:
    """Delegated to services.verification.claim_like_lines."""
    return claim_like_lines(report)


def _parse_verifier_result(verifier_result: str) -> dict[str, Any] | None:
    """Delegated to services.verification.parse_verifier_result."""
    return parse_verifier_result(verifier_result)


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
