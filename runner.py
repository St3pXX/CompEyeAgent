"""Analysis entry point — builds and invokes the LangGraph analysis graph.

``run_analysis`` keeps its original signature and ``AnalysisRunResult`` shape so
``main.py`` (CLI) and the coordinator loop's legacy path stay compatible.  The
graph performs collect -> analyze -> write -> verify with a single automatic
rewrite when provenance verification fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

from models.schema import CompetitorInput
from graph.build import build_graph
from graph.nodes import DEFAULT_EVIDENCE_INDEX


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
    """Run the analysis graph, verify provenance, and rewrite once if needed."""
    evidence_index = inputs.get("evidenceIndex", DEFAULT_EVIDENCE_INDEX)
    # Accept both a CompetitorInput-shaped dict and extra keys (e.g. evidenceIndex).
    input_data = CompetitorInput(**{
        k: v for k, v in inputs.items() if k in CompetitorInput.model_fields
    })

    initial_state = {
        "input_data": input_data,
        "evidence_index": evidence_index,
        "allow_retry": allow_retry,
        "retry_count": 0,
        "_progress": progress_callback,
    }

    graph = build_graph()
    final_state = graph.invoke(initial_state)

    if progress_callback is not None:
        progress_callback("final", "正在整理最终结果")

    report = final_state.get("report", "")
    verifier_result = final_state.get("verifier_result", "")
    scratchpad_outputs = {
        "collect/raw.json": final_state.get("collect_raw", ""),
        "analyze/findings.json": final_state.get("analyze_findings", ""),
        "write/report.md": report,
        "verify/verifier.json": verifier_result,
    }

    return AnalysisRunResult(
        report=report,
        verifier_result=verifier_result,
        passed=bool(final_state.get("passed", False)),
        retried=bool(final_state.get("retried", False)),
        scratchpad_outputs=scratchpad_outputs,
    )
