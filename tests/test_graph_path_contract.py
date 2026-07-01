"""Front-end contract test for the LangGraph execution path (module 3).

Runs a full analysis through RunService -> coordinator_loop -> graph node
executor (LLM mocked) and asserts the SSE/DAG contract the frontend depends on:
  - the required named events are emitted
  - the DAG nodes reach 'completed' with the expected scratchpad outputs
  - artifacts (report/verifier/brief/provenance) are persisted

This guards against the CrewAI->LangGraph swap silently breaking the frontend.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.coordinator import NodeExecutionResult
from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from services.run_service import RunService
from storage.coordinator_store import SQLiteCoordinatorStore
from storage.run_store import SQLiteRunStore

# Events the frontend's DashboardPage subscribes to (STREAM_EVENTS + stream.closed).
FRONTEND_STREAM_EVENTS = {
    "run.created", "run.started", "agent.started", "agent.progress",
    "agent.completed", "artifact.ready", "run.completed",
}

REPORT = (
    "## 竞品分析报告\n\n"
    "- 钉钉定价更灵活，支持免费套餐 [来源: https://example.com]\n\n"
    "## Provenance 索引\n"
    "| 来源 | URL |\n|------|-----|\n| 官网 | https://example.com |"
)
VERIFIER = '{"passed": true, "confidence": 95, "issues": []}'


def _fake_executor(*, run_id, node, context, progress_callback, foundation, **kw):
    # Emit a progress message like the real graph nodes do, so agent.progress fires.
    progress_callback(node.key, f"{node.key} 正在执行")
    outputs = {
        "collect": {"collect/raw.json": '[{"competitor": "钉钉"}]'},
        "analyze": {"analyze/findings.json": '[{"dimension": "定价"}]'},
        "write": {"write/report.md": REPORT},
        "verify": {"verify/verifier.json": VERIFIER},
    }
    refs = {
        "collect": ["collect/raw.json"], "analyze": ["analyze/findings.json"],
        "write": ["write/report.md"], "verify": ["verify/verifier.json"],
    }
    return NodeExecutionResult(
        output_refs=refs.get(node.key, []),
        scratchpad_outputs=outputs.get(node.key, {}),
    )


class GraphPathContractTest(unittest.TestCase):
    def _service(self, tmpdir):
        run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
        coord_store = SQLiteCoordinatorStore(Path(tmpdir) / "coord.sqlite3")
        coord_service = CoordinatorFoundationService(coord_store)
        return RunService(run_store, coordinator_service=coord_service), run_store, coord_store

    def test_named_events_and_dag_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service, run_store, coord_store = self._service(tmpdir)
            run = service.create_run(
                CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[])
            )
            with patch(
                "services.graph_node_executor.graph_per_node_executor",
                side_effect=_fake_executor,
            ):
                service.execute_run(run.run_id)

            emitted = {e.type for e in run_store.list_events(run.run_id)}
            missing = FRONTEND_STREAM_EVENTS - emitted
            self.assertFalse(missing, f"frontend events missing: {missing}")

            # DAG nodes all completed
            statuses = {n.key: n.status for n in coord_store.list_nodes(run.run_id)}
            for key in ("collect", "analyze", "write", "verify"):
                self.assertEqual(statuses.get(key), "completed", f"node {key} not completed")

            # run passed and artifacts persisted
            self.assertEqual(run_store.get_run(run.run_id).status, "passed")
            kinds = {a.kind for a in run_store.list_artifacts(run.run_id)}
            self.assertTrue(
                {"report_markdown", "verifier_json", "brief_json", "provenance_index"}.issubset(kinds),
                f"artifacts missing, got {kinds}",
            )

    def test_events_carry_stage_for_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service, run_store, _ = self._service(tmpdir)
            run = service.create_run(
                CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[])
            )
            with patch(
                "services.graph_node_executor.graph_per_node_executor",
                side_effect=_fake_executor,
            ):
                service.execute_run(run.run_id)

            # agent.progress events must carry a stage the frontend can map.
            stages = {
                e.stage for e in run_store.list_events(run.run_id)
                if e.type == "agent.progress" and e.stage
            }
            self.assertTrue({"collect", "analyze", "write", "verify"}.issubset(stages))


if __name__ == "__main__":
    unittest.main()
