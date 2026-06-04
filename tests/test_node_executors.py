"""Tests for services.node_executors — per-node DAG execution."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from models.coordinator import DAGNode, NodeExecutionResult, ScratchpadWriteRequest
from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from storage.coordinator_store import SQLiteCoordinatorStore


class ReadScratchpadHelperTest(unittest.TestCase):
    """Test that node executors can read upstream data from scratchpad."""

    def _make_foundation(self, tmpdir: str) -> CoordinatorFoundationService:
        store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
        return CoordinatorFoundationService(store)

    def test_read_scratchpad_returns_content(self) -> None:
        from services.node_executors import _read_scratchpad

        with tempfile.TemporaryDirectory() as tmpdir:
            foundation = self._make_foundation(tmpdir)
            foundation.write_scratchpad(
                "run-1", ScratchpadWriteRequest(path="collect/raw.json", content='{"items": []}')
            )
            result = _read_scratchpad(foundation, "run-1", "collect/raw.json")
            self.assertEqual(result, '{"items": []}')

    def test_read_scratchpad_returns_empty_for_missing(self) -> None:
        from services.node_executors import _read_scratchpad

        with tempfile.TemporaryDirectory() as tmpdir:
            foundation = self._make_foundation(tmpdir)
            result = _read_scratchpad(foundation, "run-1", "nonexistent.json")
            self.assertEqual(result, "")


class TruncateHelperTest(unittest.TestCase):
    def test_short_text_unchanged(self) -> None:
        from services.node_executors import _truncate

        self.assertEqual(_truncate("hello", max_chars=100), "hello")

    def test_long_text_truncated(self) -> None:
        from services.node_executors import _truncate

        result = _truncate("a" * 200, max_chars=100)
        self.assertEqual(len(result), 100 + len("\n\n[... 内容已截断，完整数据见 Scratchpad ...]"))
        self.assertIn("截断", result)


class PerNodeExecutorDispatchTest(unittest.TestCase):
    """Test the dispatcher routes to correct executor by node.key."""

    def _make_node(self, key: str) -> DAGNode:
        return DAGNode(
            run_id="run-1",
            key=key,
            name=f"Test {key}",
            agent=f"TestAgent_{key}",
        )

    def test_dispatches_collect(self) -> None:
        from services.node_executors import per_node_executor, _NODE_EXECUTORS

        mock_result = NodeExecutionResult()
        original = _NODE_EXECUTORS["collect"]
        try:
            _NODE_EXECUTORS["collect"] = Mock(return_value=mock_result)
            node = self._make_node("collect")
            ctx = {"input_data": Mock(), "evidence_index": "", "allow_retry": True}
            result = per_node_executor(
                run_id="run-1", node=node, context=ctx,
                progress_callback=Mock(), foundation=Mock(),
            )
            self.assertIs(result, mock_result)
            _NODE_EXECUTORS["collect"].assert_called_once()
        finally:
            _NODE_EXECUTORS["collect"] = original

    def test_dispatches_analyze(self) -> None:
        from services.node_executors import per_node_executor, _NODE_EXECUTORS

        mock_result = NodeExecutionResult()
        original = _NODE_EXECUTORS["analyze"]
        try:
            _NODE_EXECUTORS["analyze"] = Mock(return_value=mock_result)
            node = self._make_node("analyze")
            ctx = {"input_data": Mock(), "evidence_index": "", "allow_retry": True}
            result = per_node_executor(
                run_id="run-1", node=node, context=ctx,
                progress_callback=Mock(), foundation=Mock(),
            )
            self.assertIs(result, mock_result)
            _NODE_EXECUTORS["analyze"].assert_called_once()
        finally:
            _NODE_EXECUTORS["analyze"] = original

    def test_raises_for_unknown_key(self) -> None:
        from services.node_executors import per_node_executor

        node = self._make_node("unknown_stage")
        with self.assertRaises(RuntimeError) as cm:
            per_node_executor(
                run_id="run-1", node=node, context={},
                progress_callback=Mock(), foundation=Mock(),
            )
        self.assertIn("未知", str(cm.exception))


class AnalyzeExecutorRequiresScratchpadTest(unittest.TestCase):
    """Analyze executor should fail if collect/raw.json is missing."""

    @patch("services.node_executors._run_single_crew")
    def test_raises_when_collect_output_missing(self, _mock_crew: Mock) -> None:
        from services.node_executors import _execute_analyze

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            foundation = CoordinatorFoundationService(store)
            node = DAGNode(run_id="run-1", key="analyze", name="Analyze", agent="Analyzer")

            with self.assertRaises(RuntimeError) as cm:
                _execute_analyze(
                    run_id="run-1", node=node,
                    context={},
                    progress_callback=Mock(),
                    foundation=foundation,
                )
            self.assertIn("collect/raw.json", str(cm.exception))


class WriteExecutorRequiresScratchpadTest(unittest.TestCase):
    @patch("services.node_executors._run_single_crew")
    def test_raises_when_findings_missing(self, _mock_crew: Mock) -> None:
        from services.node_executors import _execute_write

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            foundation = CoordinatorFoundationService(store)
            node = DAGNode(run_id="run-1", key="write", name="Write", agent="Writer")

            with self.assertRaises(RuntimeError) as cm:
                _execute_write(
                    run_id="run-1", node=node,
                    context={},
                    progress_callback=Mock(),
                    foundation=foundation,
                )
            self.assertIn("analyze/findings.json", str(cm.exception))


class VerifyExecutorRequiresScratchpadTest(unittest.TestCase):
    @patch("services.node_executors._run_single_crew")
    def test_raises_when_report_missing(self, _mock_crew: Mock) -> None:
        from services.node_executors import _execute_verify

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            foundation = CoordinatorFoundationService(store)
            node = DAGNode(run_id="run-1", key="verify", name="Verify", agent="Verifier")

            with self.assertRaises(RuntimeError) as cm:
                _execute_verify(
                    run_id="run-1", node=node,
                    context={},
                    progress_callback=Mock(),
                    foundation=foundation,
                )
            self.assertIn("write/report.md", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
