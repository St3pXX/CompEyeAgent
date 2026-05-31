import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import api_app
from models.coordinator import ScratchpadWriteRequest
from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
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


if __name__ == "__main__":
    unittest.main()
