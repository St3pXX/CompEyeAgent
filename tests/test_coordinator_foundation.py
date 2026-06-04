import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import api_app
from models.coordinator import NodeExecutionResult, ScratchpadWriteRequest
from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from services.coordinator_loop import CoordinatorLoopService
from services.run_service import RunService
from storage.coordinator_store import SQLiteCoordinatorStore
from storage.run_store import SQLiteRunStore


class CoordinatorFoundationTest(unittest.TestCase):
    def test_default_dag_and_input_scratchpad_are_created_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            service = CoordinatorFoundationService(store)
            input_data = {"productName": "飞书", "competitors": ["钉钉"], "dimensions": []}

            first = service.ensure_default_dag("run-1", input_data)
            second = service.ensure_default_dag("run-1", input_data)

            self.assertEqual([node.key for node in first.nodes], ["collect", "analyze", "write", "verify"])
            self.assertEqual([(edge.source, edge.target) for edge in first.edges], [("collect", "analyze"), ("analyze", "write"), ("write", "verify")])
            self.assertEqual(len(second.nodes), 4)
            self.assertEqual(store.list_scratchpad_items("run-1")[0].path, "input/brief.json")

    def test_scratchpad_write_upserts_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            service = CoordinatorFoundationService(store)

            service.write_scratchpad("run-1", ScratchpadWriteRequest(path="collect/raw.json", content='{"items": []}'))
            service.write_scratchpad("run-1", ScratchpadWriteRequest(path="collect/raw.json", content='{"items": [1]}'))

            items = service.list_scratchpad("run-1")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].content, '{"items": [1]}')
            self.assertEqual(items[0].content_preview, '{"items": [1]}')

    def test_api_exposes_dag_scratchpad_and_inspector(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            api_app.store = run_store
            api_app.coordinator_store = coordinator_store
            api_app.coordinator_service = CoordinatorFoundationService(coordinator_store)
            client = TestClient(api_app.app)
            run = run_store.create_run(
                CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump()
            )

            dag_response = client.get(f"/api/runs/{run.run_id}/dag")
            write_response = client.post(
                f"/api/runs/{run.run_id}/scratchpad",
                json={"path": "collect/raw.json", "kind": "json", "content": '{"items": []}'},
            )
            scratchpad_response = client.get(f"/api/runs/{run.run_id}/scratchpad")
            inspector_response = client.get(f"/api/runs/{run.run_id}/inspector")

            self.assertEqual(dag_response.status_code, 200)
            self.assertEqual(write_response.status_code, 201)
            self.assertEqual(len(dag_response.json()["dag"]["nodes"]), 4)
            paths = {item["path"] for item in scratchpad_response.json()["items"]}
            self.assertEqual(paths, {"input/brief.json", "collect/raw.json"})
            self.assertEqual(inspector_response.json()["inspector"]["dag"]["node_count"], 4)

    def test_run_service_creates_dag_when_run_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            service = RunService(run_store, coordinator_service=coordinator_service)

            run = service.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]))

            self.assertEqual([node.key for node in coordinator_store.list_nodes(run.run_id)], ["collect", "analyze", "write", "verify"])
            self.assertEqual(coordinator_store.list_scratchpad_items(run.run_id)[0].path, "input/brief.json")

    def test_run_service_updates_dag_status_from_progress_callbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            service = RunService(run_store, coordinator_service=coordinator_service)
            run = service.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]))

            coordinator_service.mark_stage_running(run.run_id, "collect")
            coordinator_service.mark_stage_running(run.run_id, "analyze")
            coordinator_service.mark_stage_running(run.run_id, "write")
            coordinator_service.mark_stage_running(run.run_id, "verify")
            coordinator_service.mark_run_finished(run.run_id, passed=True)

            statuses = {node.key: node.status for node in coordinator_store.list_nodes(run.run_id)}
            self.assertEqual(statuses, {"collect": "completed", "analyze": "completed", "write": "completed", "verify": "completed"})

    def test_run_failure_marks_verify_failed_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            service = RunService(run_store, coordinator_service=coordinator_service)
            run = service.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]))

            coordinator_service.mark_run_failed(run.run_id)

            statuses = {node.key: node.status for node in coordinator_store.list_nodes(run.run_id)}
            self.assertEqual(statuses["verify"], "failed")

    def test_record_execution_outputs_writes_scratchpad_and_node_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            service = CoordinatorFoundationService(store)
            service.ensure_default_dag("run-1", {"productName": "飞书"})

            service.record_execution_outputs(
                "run-1",
                report_markdown="# 报告",
                verifier_json='{"passed": true}',
                provenance_json="[]",
            )

            items = {item.path: item for item in service.list_scratchpad("run-1")}
            write_node = store.get_node("run-1", "write")
            verify_node = store.get_node("run-1", "verify")
            self.assertEqual(items["write/report.md"].content, "# 报告")
            self.assertEqual(items["verify/verifier.json"].content, '{"passed": true}')
            self.assertEqual(write_node.output_refs, ["write/report.md"])
            self.assertEqual(verify_node.input_refs, ["write/report.md"])
            self.assertEqual(verify_node.output_refs, ["verify/verifier.json", "verify/provenance_index.json"])

    def test_record_stage_outputs_writes_intermediate_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            service = CoordinatorFoundationService(store)
            service.ensure_default_dag("run-1", {"productName": "飞书"})

            service.record_stage_outputs(
                "run-1",
                {
                    "collect/raw.json": '[{"competitor": "钉钉"}]',
                    "analyze/findings.json": '[{"dimension": "定价"}]',
                },
            )

            items = {item.path: item for item in service.list_scratchpad("run-1")}
            collect_node = store.get_node("run-1", "collect")
            analyze_node = store.get_node("run-1", "analyze")
            self.assertEqual(items["collect/raw.json"].kind, "json")
            self.assertEqual(items["analyze/findings.json"].kind, "json")
            self.assertEqual(collect_node.output_refs, ["collect/raw.json"])
            self.assertEqual(analyze_node.output_refs, ["analyze/findings.json"])

    def test_run_service_records_execution_outputs_to_scratchpad(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            service = RunService(run_store, coordinator_service=coordinator_service)
            run = service.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]))

            report = (
                "## 竞品分析报告\n\n"
                "- 钉钉定价更灵活 [来源: https://example.com]\n\n"
                "## Provenance 索引\n"
                "| 来源 | URL |\n|------|-----|\n| 官网 | https://example.com |"
            )
            verifier = '{"passed": true, "confidence": 95, "issues": []}'

            # Mock per_node_executor to return scratchpad outputs for each node
            def fake_executor(*, run_id, node, context, progress_callback, foundation, **kw):
                outputs = {
                    "collect": {"collect/raw.json": '[{"competitor": "钉钉"}]'},
                    "analyze": {"analyze/findings.json": '[{"dimension": "定价"}]'},
                    "write": {"write/report.md": report},
                    "verify": {"verify/verifier.json": verifier},
                }
                return NodeExecutionResult(scratchpad_outputs=outputs.get(node.key, {}))

            with patch("services.node_executors.per_node_executor", side_effect=fake_executor):
                service.execute_run(run.run_id)

            paths = {item.path for item in coordinator_service.list_scratchpad(run.run_id)}
            verify_node = coordinator_store.get_node(run.run_id, "verify")
            collect_node = coordinator_store.get_node(run.run_id, "collect")
            analyze_node = coordinator_store.get_node(run.run_id, "analyze")
            self.assertTrue(
                {
                    "input/brief.json",
                    "collect/raw.json",
                    "analyze/findings.json",
                    "write/report.md",
                    "verify/verifier.json",
                    "verify/provenance_index.json",
                }.issubset(paths)
            )
            self.assertEqual(collect_node.output_refs, ["collect/raw.json"])
            self.assertEqual(analyze_node.output_refs, ["analyze/findings.json"])
            self.assertEqual(verify_node.output_refs, ["verify/verifier.json", "verify/provenance_index.json"])

    def test_run_service_executes_through_coordinator_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            service = RunService(run_store, coordinator_service=coordinator_service)
            run = service.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]))

            report = (
                "## 竞品分析报告\n\n"
                "- 钉钉定价更灵活，支持免费套餐 [来源: https://example.com]\n\n"
                "## Provenance 索引\n"
                "| 来源 | URL |\n|------|-----|\n| 官网 | https://example.com |"
            )
            verifier = '{"passed": true, "confidence": 95, "issues": []}'

            def fake_executor(*, run_id, node, context, progress_callback, foundation, **kw):
                outputs = {
                    "collect": {"collect/raw.json": "[]"},
                    "write": {"write/report.md": report},
                    "verify": {"verify/verifier.json": verifier},
                }
                return NodeExecutionResult(scratchpad_outputs=outputs.get(node.key, {}))

            with patch("services.node_executors.per_node_executor", side_effect=fake_executor):
                service.execute_run(run.run_id)

            events = run_store.list_events(run.run_id)
            statuses = {node.key: node.status for node in coordinator_store.list_nodes(run.run_id)}
            self.assertEqual(run_store.get_run(run.run_id).status, "passed")
            self.assertIn("Coordinator 主循环开始执行", [event.message for event in events])
            self.assertEqual(statuses["verify"], "completed")
            self.assertTrue(any(item.path == "collect/raw.json" for item in coordinator_service.list_scratchpad(run.run_id)))

    def test_coordinator_loop_marks_failed_run_and_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            service = RunService(run_store, coordinator_service=coordinator_service)
            run = service.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]))

            with patch("services.node_executors.per_node_executor", side_effect=RuntimeError("boom")):
                service.execute_run(run.run_id)

            statuses = {node.key: node.status for node in coordinator_store.list_nodes(run.run_id)}
            self.assertEqual(run_store.get_run(run.run_id).status, "failed")
            self.assertEqual(statuses["collect"], "failed")
            self.assertEqual(statuses["analyze"], "skipped")
            self.assertEqual(statuses["write"], "skipped")
            self.assertEqual(statuses["verify"], "skipped")

    def test_coordinator_loop_schedules_ready_nodes_in_dependency_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            loop = CoordinatorLoopService(run_store, coordinator_service)
            run = run_store.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump())
            coordinator_service.ensure_default_dag(run.run_id, run.input.model_dump())
            calls: list[str] = []
            result = SimpleNamespace(
                report="报告 [来源: https://example.com]",
                verifier_result='{"passed": true, "confidence": 95, "issues": []}',
                passed=True,
                retried=False,
                scratchpad_outputs={},
            )

            def node_executor(**kwargs: object) -> NodeExecutionResult:
                node = kwargs["node"]
                calls.append(node.key)
                if node.key == "verify":
                    return NodeExecutionResult(final_result=result)
                return NodeExecutionResult(output_refs=[f"{node.key}/output.txt"], scratchpad_outputs={f"{node.key}/output.txt": node.key})

            loop.execute(
                run.run_id,
                input_data=run.input,
                allow_retry=True,
                evidence_index="Evidence Index",
                run_analysis=Mock(),
                node_executor=node_executor,
            )

            statuses = {node.key: node.status for node in coordinator_store.list_nodes(run.run_id)}
            self.assertEqual(calls, ["collect", "analyze", "write", "verify"])
            self.assertEqual(statuses, {"collect": "completed", "analyze": "completed", "write": "completed", "verify": "completed"})
            self.assertEqual(run_store.get_run(run.run_id).status, "passed")

    def test_coordinator_loop_retries_failed_node_before_failing_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            loop = CoordinatorLoopService(run_store, coordinator_service)
            run = run_store.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump())
            coordinator_service.ensure_default_dag(run.run_id, run.input.model_dump())
            attempts = {"collect": 0}
            result = SimpleNamespace(
                report="报告 [来源: https://example.com]",
                verifier_result='{"passed": true, "confidence": 95, "issues": []}',
                passed=True,
                retried=False,
                scratchpad_outputs={},
            )

            def node_executor(**kwargs: object) -> NodeExecutionResult:
                node = kwargs["node"]
                if node.key == "collect":
                    attempts["collect"] += 1
                    if attempts["collect"] == 1:
                        raise RuntimeError("temporary collect failure")
                if node.key == "verify":
                    return NodeExecutionResult(final_result=result)
                return NodeExecutionResult()

            loop.execute(
                run.run_id,
                input_data=run.input,
                allow_retry=True,
                evidence_index="Evidence Index",
                run_analysis=Mock(),
                node_executor=node_executor,
            )

            collect_node = coordinator_store.get_node(run.run_id, "collect")
            retry_events = [event for event in run_store.list_events(run.run_id) if event.type == "agent.retrying"]
            self.assertEqual(attempts["collect"], 2)
            self.assertEqual(collect_node.metadata["retry_attempts"], 2)
            self.assertEqual(len(retry_events), 1)
            self.assertEqual(run_store.get_run(run.run_id).status, "passed")

    def test_cancelled_run_does_not_enter_coordinator_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            service = RunService(run_store, coordinator_service=coordinator_service)
            run = service.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]))
            service.cancel_run(run.run_id)
            run_analysis = Mock()
            fake_runner = SimpleNamespace(run_analysis=run_analysis)

            with patch.dict("sys.modules", {"runner": fake_runner}):
                service.execute_run(run.run_id)

            run_analysis.assert_not_called()
            self.assertEqual(run_store.get_run(run.run_id).status, "cancelled")


if __name__ == "__main__":
    unittest.main()
