import json
import re
from dataclasses import dataclass
from typing import Any

from crew import analysis_crew
from crewai import Crew
from crew.agents.verifier import verifier
from crew.agents.writer import writer
from tasks.verify_task import verify_task
from tasks.write_task import write_task


SOURCE_MARKERS = ("[来源:", "source_references", "provenance", "来源 URL", "来源:")


@dataclass
class AnalysisRunResult:
    report: str
    verifier_result: str
    passed: bool
    retried: bool = False


def run_analysis(inputs: dict[str, Any]) -> AnalysisRunResult:
    """Run the Phase 1 chain, verify provenance, and rewrite once if needed."""
    kickoff_result = analysis_crew.kickoff(inputs=inputs)
    report = _task_output(write_task, fallback=kickoff_result)
    verifier_result = _task_output(verify_task, fallback=kickoff_result)
    issues = _verification_issues(report, verifier_result)

    if not issues:
        return AnalysisRunResult(
            report=report,
            verifier_result=verifier_result,
            passed=True,
        )

    retry_result, retry_write_task, retry_verify_task = _rewrite_and_verify(inputs, issues)
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

    if not _has_sources(report):
        issues.append("最终报告缺少来源标注或 provenance 索引")

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


def _has_sources(report: str) -> bool:
    if any(marker in report for marker in SOURCE_MARKERS):
        return True
    return bool(re.search(r"https?://\S+", report))


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
