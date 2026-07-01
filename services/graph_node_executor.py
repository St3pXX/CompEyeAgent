"""Graph-backed per-node executor for the coordinator loop.

Drop-in replacement for ``services.node_executors.per_node_executor`` that runs
each DAG node via the LangGraph node functions (``graph/nodes.py``) instead of
single-node CrewAI crews.  The coordinator loop keeps owning orchestration,
events, DAG state, heartbeat, and persistence — this only swaps *how* a node's
LLM work is performed, removing CrewAI from the API execution path.

Upstream outputs are read from the scratchpad (as before); the graph node
functions receive them via a lightweight state dict and the progress callback
via ``state["_progress"]``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from models.coordinator import DAGNode, NodeExecutionResult
from services.coordinator_foundation import CoordinatorFoundationService
from graph.nodes import (
    DEFAULT_EVIDENCE_INDEX,
    analyze_node,
    collect_node,
    verify_node,
    write_node,
)
from graph.state import AnalysisState


def _read(foundation: CoordinatorFoundationService, run_id: str, path: str) -> str:
    try:
        return foundation.store.get_scratchpad_item(run_id, path).content
    except Exception:
        return ""


def graph_per_node_executor(
    *,
    run_id: str,
    node: DAGNode,
    context: dict[str, Any],
    progress_callback: Callable[[str, str], None],
    foundation: CoordinatorFoundationService,
    **_kwargs: Any,
) -> NodeExecutionResult:
    """Execute a single DAG node using the corresponding graph node function."""
    input_data = context["input_data"]
    evidence_index = context.get("evidence_index", DEFAULT_EVIDENCE_INDEX)

    state: AnalysisState = {
        "input_data": input_data,
        "evidence_index": evidence_index,
        "run_id": run_id,
        "_progress": progress_callback,
    }

    key = node.key
    if key == "collect":
        update = collect_node(state)
        return NodeExecutionResult(
            output_refs=["collect/raw.json"],
            scratchpad_outputs={"collect/raw.json": update["collect_raw"]},
        )
    if key == "analyze":
        state["collect_raw"] = _read(foundation, run_id, "collect/raw.json")
        if not state["collect_raw"]:
            raise RuntimeError("collect/raw.json 不存在于 Scratchpad 中，无法执行分析")
        update = analyze_node(state)
        return NodeExecutionResult(
            output_refs=["analyze/findings.json"],
            scratchpad_outputs={"analyze/findings.json": update["analyze_findings"]},
        )
    if key == "write":
        state["analyze_findings"] = _read(foundation, run_id, "analyze/findings.json")
        if not state["analyze_findings"]:
            raise RuntimeError("analyze/findings.json 不存在于 Scratchpad 中，无法撰写报告")
        update = write_node(state)
        return NodeExecutionResult(
            output_refs=["write/report.md"],
            scratchpad_outputs={"write/report.md": update["report"]},
        )
    if key == "verify":
        state["report"] = _read(foundation, run_id, "write/report.md")
        if not state["report"]:
            raise RuntimeError("write/report.md 不存在于 Scratchpad 中，无法执行质检")
        update = verify_node(state)
        return NodeExecutionResult(
            output_refs=["verify/verifier.json"],
            scratchpad_outputs={"verify/verifier.json": update["verifier_result"]},
        )

    raise RuntimeError(f"未知的 DAG 节点类型：{key}")
