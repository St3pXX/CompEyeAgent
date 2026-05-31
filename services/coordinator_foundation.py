"""Foundation service for Phase 2 DAG and scratchpad state."""

from __future__ import annotations

import json
from typing import Any

from models.coordinator import DAGEdge, DAGNode, DAGView, ScratchpadItem, ScratchpadWriteRequest
from storage.coordinator_store import SQLiteCoordinatorStore


DEFAULT_DAG_TEMPLATE = (
    {"key": "collect", "name": "Collect public evidence", "agent": "Collector", "depends_on": []},
    {"key": "analyze", "name": "Analyze competitive findings", "agent": "Analyzer", "depends_on": ["collect"]},
    {"key": "write", "name": "Write report", "agent": "Writer", "depends_on": ["analyze"]},
    {"key": "verify", "name": "Verify report quality", "agent": "Verifier", "depends_on": ["write"]},
)


class CoordinatorFoundationService:
    def __init__(self, store: SQLiteCoordinatorStore) -> None:
        self.store = store

    def ensure_default_dag(self, run_id: str, input_data: dict[str, Any]) -> DAGView:
        if not self.store.list_nodes(run_id):
            for node in DEFAULT_DAG_TEMPLATE:
                self.store.upsert_node(
                    DAGNode(
                        run_id=run_id,
                        key=node["key"],
                        name=node["name"],
                        agent=node["agent"],
                        depends_on=list(node["depends_on"]),
                        metadata={"template": "phase2-coordinator-foundation:v1"},
                    )
                )
            self.write_scratchpad(
                run_id,
                ScratchpadWriteRequest(
                    path="input/brief.json",
                    kind="json",
                    content=json.dumps(input_data, ensure_ascii=False, indent=2),
                    metadata={"source": "run.input"},
                ),
            )
        return self.get_dag(run_id)

    def get_dag(self, run_id: str) -> DAGView:
        nodes = self.store.list_nodes(run_id)
        return DAGView(run_id=run_id, nodes=nodes, edges=_edges_from_nodes(nodes))

    def mark_stage_running(self, run_id: str, stage: str) -> None:
        stage_key = _stage_to_node_key(stage)
        if stage_key is None:
            return
        nodes = {node.key: node for node in self.store.list_nodes(run_id)}
        if stage_key not in nodes:
            return
        for dependency in nodes[stage_key].depends_on:
            if dependency in nodes and nodes[dependency].status in {"pending", "running"}:
                self.store.update_node_status(run_id, dependency, "completed")
        if nodes[stage_key].status == "pending":
            self.store.update_node_status(run_id, stage_key, "running")

    def mark_run_finished(self, run_id: str, *, passed: bool) -> None:
        nodes = self.store.list_nodes(run_id)
        status_by_key = {node.key: node.status for node in nodes}
        for node in nodes:
            if node.key == "verify":
                self.store.update_node_status(run_id, node.key, "completed" if passed else "failed")
            elif status_by_key.get(node.key) in {"pending", "running"}:
                self.store.update_node_status(run_id, node.key, "completed")

    def mark_run_failed(self, run_id: str, stage: str | None = None) -> None:
        stage_key = _stage_to_node_key(stage or "") or "verify"
        nodes = {node.key: node for node in self.store.list_nodes(run_id)}
        if stage_key in nodes:
            self.store.update_node_status(run_id, stage_key, "failed")

    def record_execution_outputs(
        self,
        run_id: str,
        *,
        report_markdown: str,
        verifier_json: str,
        provenance_json: str,
    ) -> None:
        self.write_scratchpad(
            run_id,
            ScratchpadWriteRequest(
                path="write/report.md",
                kind="markdown",
                content=report_markdown,
                producer_node_id=self._node_id(run_id, "write"),
                metadata={"source": "artifact.report_markdown"},
            ),
        )
        self.write_scratchpad(
            run_id,
            ScratchpadWriteRequest(
                path="verify/verifier.json",
                kind="json",
                content=verifier_json,
                producer_node_id=self._node_id(run_id, "verify"),
                metadata={"source": "artifact.verifier_json"},
            ),
        )
        self.write_scratchpad(
            run_id,
            ScratchpadWriteRequest(
                path="verify/provenance_index.json",
                kind="json",
                content=provenance_json,
                producer_node_id=self._node_id(run_id, "verify"),
                metadata={"source": "artifact.provenance_index"},
            ),
        )
        self.store.update_node_refs(run_id, "write", output_refs=["write/report.md"])
        self.store.update_node_refs(
            run_id,
            "verify",
            input_refs=["write/report.md"],
            output_refs=["verify/verifier.json", "verify/provenance_index.json"],
        )

    def write_scratchpad(self, run_id: str, request: ScratchpadWriteRequest) -> ScratchpadItem:
        return self.store.write_scratchpad_item(
            ScratchpadItem(
                run_id=run_id,
                path=request.path,
                kind=request.kind,
                content=request.content,
                producer_node_id=request.producer_node_id,
                metadata=request.metadata,
            )
        )

    def list_scratchpad(self, run_id: str) -> list[ScratchpadItem]:
        return self.store.list_scratchpad_items(run_id)

    def inspector_summary(self, run_id: str) -> dict[str, object]:
        nodes = self.store.list_nodes(run_id)
        scratchpad_items = self.store.list_scratchpad_items(run_id)
        status_counts: dict[str, int] = {}
        for node in nodes:
            status_counts[node.status] = status_counts.get(node.status, 0) + 1
        return {
            "run_id": run_id,
            "dag": {"node_count": len(nodes), "status_counts": status_counts},
            "scratchpad": {"item_count": len(scratchpad_items), "paths": [item.path for item in scratchpad_items]},
        }

    def _node_id(self, run_id: str, key: str) -> str | None:
        try:
            return self.store.get_node(run_id, key).node_id
        except KeyError:
            return None


def _edges_from_nodes(nodes: list[DAGNode]) -> list[DAGEdge]:
    edges: list[DAGEdge] = []
    keys = {node.key for node in nodes}
    for node in nodes:
        for dependency in node.depends_on:
            if dependency in keys:
                edges.append(DAGEdge(source=dependency, target=node.key))
    return edges


def _stage_to_node_key(stage: str) -> str | None:
    if stage == "rewrite":
        return "write"
    if stage in {"collect", "analyze", "write", "verify"}:
        return stage
    return None
