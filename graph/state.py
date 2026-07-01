"""Graph state definition for the CompEye analysis pipeline.

The state carries the user input plus each stage's scratchpad output.  Field
names map to the legacy scratchpad keys and ``runner.AnalysisRunResult`` so the
rest of the app (api_app, frontend) sees an unchanged result shape.
"""

from __future__ import annotations

from typing import Any, TypedDict

from models.schema import CompetitorInput


class AnalysisState(TypedDict, total=False):
    """State threaded through the collect -> analyze -> write -> verify graph.

    Scratchpad-aligned outputs:
        collect_raw       -> scratchpad "collect/raw.json"
        analyze_findings  -> scratchpad "analyze/findings.json"
        report            -> scratchpad "write/report.md"
        verifier_result   -> scratchpad "verify/verifier.json"
    """

    # Inputs
    input_data: CompetitorInput
    evidence_index: str
    allow_retry: bool
    run_id: str

    # Stage outputs
    collect_raw: str
    analyze_findings: str
    report: str
    verifier_result: str

    # Verification / control flow
    issues: list[str]
    retry_count: int
    passed: bool
    retried: bool

    # Progress callback (stage, message) -> None; optional, not persisted meaningfully
    _progress: Any
