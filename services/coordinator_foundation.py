"""Foundation service for Phase 2 DAG and scratchpad state."""

from __future__ import annotations

import json
from typing import Any

from models.coordinator import DAGEdge, DAGNode, DAGView, ScratchpadItem, ScratchpadWriteRequest
from storage.protocols import CoordinatorStoreProtocol


DEFAULT_DAG_TEMPLATE = (
    {"key": "collect", "name": "Collect public evidence", "agent": "Collector", "depends_on": []},
    {"key": "analyze", "name": "Analyze competitive findings", "agent": "Analyzer", "depends_on": ["collect"]},
    {"key": "write", "name": "Write report", "agent": "Writer", "depends_on": ["analyze"]},
    {"key": "verify", "name": "Verify report quality", "agent": "Verifier", "depends_on": ["write"]},
)


class CoordinatorFoundationService:
    def __init__(self, store: CoordinatorStoreProtocol) -> None:
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
            self.mark_descendants_skipped(run_id, stage_key)

    def mark_descendants_skipped(self, run_id: str, key: str) -> None:
        nodes = {node.key: node for node in self.store.list_nodes(run_id)}
        descendants = _descendant_keys(nodes, key)
        for descendant in descendants:
            if nodes[descendant].status in {"pending", "running"}:
                self.store.update_node_status(run_id, descendant, "skipped")

    def reset_node_for_retry(self, run_id: str, key: str) -> None:
        nodes = {node.key: node for node in self.store.list_nodes(run_id)}
        if key not in nodes:
            raise KeyError(key)
        retry_keys = [key, *_descendant_keys(nodes, key)]
        for retry_key in retry_keys:
            self.store.update_node_status(run_id, retry_key, "pending")
            node = self.store.get_node(run_id, retry_key)
            metadata = dict(node.metadata)
            metadata.pop("last_error", None)
            metadata["retry_attempts"] = 0
            self.store.update_node_metadata(run_id, retry_key, metadata)

    def record_execution_outputs(
        self,
        run_id: str,
        *,
        report_markdown: str,
        verifier_json: str,
        provenance_json: str,
        stage_outputs: dict[str, str] | None = None,
    ) -> None:
        self.record_stage_outputs(run_id, stage_outputs or {})
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

    def record_stage_outputs(self, run_id: str, stage_outputs: dict[str, str]) -> None:
        stage_map = {
            "collect/raw.json": ("collect", "json"),
            "analyze/findings.json": ("analyze", "json"),
            "write/report.md": ("write", "markdown"),
            "write/retry_report.md": ("write", "markdown"),
            "verify/verifier.json": ("verify", "json"),
            "verify/retry_verifier.json": ("verify", "json"),
        }
        refs_by_node: dict[str, list[str]] = {}
        for path, content in stage_outputs.items():
            if not content:
                continue
            node_key, kind = stage_map.get(path, ("collect", "text"))
            self.write_scratchpad(
                run_id,
                ScratchpadWriteRequest(
                    path=path,
                    kind=kind,  # type: ignore[arg-type]
                    content=content,
                    producer_node_id=self._node_id(run_id, node_key),
                    metadata={"source": "runner.task_output"},
                ),
            )
            refs_by_node.setdefault(node_key, []).append(path)

        for node_key, refs in refs_by_node.items():
            node = self.store.get_node(run_id, node_key)
            merged_refs = [*node.output_refs]
            for ref in refs:
                if ref not in merged_refs:
                    merged_refs.append(ref)
            self.store.update_node_refs(run_id, node_key, output_refs=merged_refs)

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

    def update_node_metadata(self, run_id: str, key: str, metadata: dict[str, object]) -> DAGNode:
        return self.store.update_node_metadata(run_id, key, metadata)


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


def _descendant_keys(nodes: dict[str, DAGNode], key: str) -> list[str]:
    descendants: list[str] = []
    pending = [key]
    while pending:
        parent = pending.pop(0)
        for node in nodes.values():
            if node.key in descendants:
                continue
            if parent in node.depends_on:
                descendants.append(node.key)
                pending.append(node.key)
    return descendants
