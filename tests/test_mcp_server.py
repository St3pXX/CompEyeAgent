"""Tests for mcp_server — MCP tool functions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.schema import CompetitorInput


class McpServerToolsTest(unittest.TestCase):
    """Test MCP tool functions by calling them directly."""

    def setUp(self) -> None:
        """Create isolated stores in a temp directory."""
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        from storage.run_store import SQLiteRunStore
        from storage.coordinator_store import SQLiteCoordinatorStore
        from services.coordinator_foundation import CoordinatorFoundationService
        self._store = SQLiteRunStore(tmp / "runs.sqlite3")
        self._coord_store = SQLiteCoordinatorStore(tmp / "coord.sqlite3")
        self._coord_svc = CoordinatorFoundationService(self._coord_store)

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def _patch_stores(self):
        """Return a dict of patches for mcp_server module-level stores."""
        import mcp_server
        return {
            "store": patch.object(mcp_server, "store", self._store),
            "coordinator_store": patch.object(mcp_server, "coordinator_store", self._coord_store),
            "coordinator_service": patch.object(mcp_server, "coordinator_service", self._coord_svc),
            "run_service": patch.object(mcp_server, "_run_service", None),
        }

    def test_list_runs_empty(self) -> None:
        import mcp_server
        with self._patch_stores()["store"], self._patch_stores()["run_service"]:
            result = json.loads(mcp_server.list_runs())
            self.assertEqual(result["runs"], [])

    def test_create_run_returns_run_id(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            result = json.loads(mcp_server.create_run(
                product_name="飞书",
                competitors=["钉钉"],
                dimensions=[{"name": "定价", "indicators": ["免费套餐"]}],
            ))
            self.assertIn("run_id", result)
            self.assertEqual(result["status"], "queued")

    def test_get_run_returns_status(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            result = json.loads(mcp_server.create_run(
                product_name="飞书", competitors=["钉钉"], dimensions=[],
            ))
            run_id = result["run_id"]
            detail = json.loads(mcp_server.get_run(run_id))
            self.assertEqual(detail["run_id"], run_id)
            self.assertEqual(detail["product"], "飞书")

    def test_get_run_not_found(self) -> None:
        import mcp_server
        with self._patch_stores()["store"]:
            result = json.loads(mcp_server.get_run("nonexistent"))
            self.assertIn("error", result)

    def test_list_runs_after_create(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            mcp_server.create_run(product_name="飞书", competitors=["钉钉"], dimensions=[])
            result = json.loads(mcp_server.list_runs())
            self.assertEqual(len(result["runs"]), 1)

    def test_get_report_not_ready(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            result = json.loads(mcp_server.create_run(
                product_name="飞书", competitors=["钉钉"], dimensions=[],
            ))
            run_id = result["run_id"]
            report = json.loads(mcp_server.get_report(run_id))
            self.assertIn("error", report)

    def test_get_verification_not_ready(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            result = json.loads(mcp_server.create_run(
                product_name="飞书", competitors=["钉钉"], dimensions=[],
            ))
            run_id = result["run_id"]
            verification = json.loads(mcp_server.get_verification(run_id))
            self.assertIn("error", verification)

    def test_get_sources_empty(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            result = json.loads(mcp_server.create_run(
                product_name="飞书", competitors=["钉钉"], dimensions=[],
            ))
            run_id = result["run_id"]
            sources = json.loads(mcp_server.get_sources(run_id))
            self.assertEqual(sources["sources"], [])

    def test_get_scratchpad(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            result = json.loads(mcp_server.create_run(
                product_name="飞书", competitors=["钉钉"], dimensions=[],
            ))
            run_id = result["run_id"]
            sp = json.loads(mcp_server.get_scratchpad(run_id))
            self.assertIn("items", sp)

    def test_cancel_run(self) -> None:
        import mcp_server
        patches = self._patch_stores()
        with patches["store"], patches["coordinator_store"], patches["coordinator_service"], patches["run_service"]:
            result = json.loads(mcp_server.create_run(
                product_name="飞书", competitors=["钉钉"], dimensions=[],
            ))
            run_id = result["run_id"]
            cancel = json.loads(mcp_server.cancel_run(run_id))
            self.assertEqual(cancel["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
