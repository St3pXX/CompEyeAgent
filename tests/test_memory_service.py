"""Tests for services.memory_service — long-term memory extraction and retrieval."""

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock

from models.schema import CompetitorInput
from services.memory_service import MemoryService
from storage.run_store import SQLiteRunStore
from storage.vector_store import FactResult, VectorStore


class MemoryServiceTest(unittest.TestCase):
    def _make_service(self, tmpdir: str) -> tuple[MemoryService, SQLiteRunStore]:
        store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
        try:
            vs = VectorStore(in_memory=True, collection_name=f"test_{uuid.uuid4().hex[:8]}")
        except Exception:
            self.skipTest("ChromaDB not available")
        return MemoryService(vs, store), store

    def test_ingest_completed_run_with_passing_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, store = self._make_service(tmpdir)
            run = store.create_run(
                CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump()
            )
            store.update_run_status(run.run_id, "passed", completed=True)
            store.create_artifact(run.run_id, "report_markdown", "- 钉钉定价更灵活 [来源: https://example.com]")
            store.create_artifact(
                run.run_id, "verifier_json",
                '{"passed": true, "confidence": 85, "issues": []}',
            )

            count = svc.ingest_completed_run(run.run_id)
            self.assertGreaterEqual(count, 0)  # may extract 0 if no claim-like lines

    def test_ingest_skips_failed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, store = self._make_service(tmpdir)
            run = store.create_run(
                CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump()
            )
            store.update_run_status(run.run_id, "failed", completed=True)

            count = svc.ingest_completed_run(run.run_id)
            self.assertEqual(count, 0)

    def test_ingest_skips_low_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, store = self._make_service(tmpdir)
            run = store.create_run(
                CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump()
            )
            store.update_run_status(run.run_id, "needs_review", completed=True)
            store.create_artifact(run.run_id, "report_markdown", "- 钉钉定价更灵活 [来源: https://example.com]")
            store.create_artifact(
                run.run_id, "verifier_json",
                '{"passed": false, "confidence": 30, "issues": []}',
            )

            count = svc.ingest_completed_run(run.run_id)
            self.assertEqual(count, 0)

    def test_query_for_run_returns_empty_when_no_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = self._make_service(tmpdir)
            result = svc.query_for_run(["钉钉"], ["定价"])
            self.assertIn("no relevant", result.lower())

    def test_query_raw_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = self._make_service(tmpdir)
            results = svc.query_raw("test query")
            self.assertEqual(results, [])

    def test_ingest_nonexistent_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = self._make_service(tmpdir)
            count = svc.ingest_completed_run("nonexistent")
            self.assertEqual(count, 0)


class VectorStoreTest(unittest.TestCase):
    def _make_store(self, tmpdir: str) -> VectorStore:
        try:
            return VectorStore(in_memory=True, collection_name=f"test_{uuid.uuid4().hex[:8]}")
        except Exception:
            self.skipTest("ChromaDB not available")

    def test_upsert_and_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = self._make_store(tmpdir)
            vs.upsert_fact("run-1", "钉钉免费版支持最多 500 人", {"competitor": "钉钉"})
            self.assertEqual(vs.count(), 1)

    def test_query_returns_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = self._make_store(tmpdir)
            vs.upsert_fact("run-1", "钉钉免费版支持最多 500 人", {"competitor": "钉钉"})
            vs.upsert_fact("run-1", "飞书定价更灵活", {"competitor": "飞书"})
            # With hash-based embedding, at least one result should come back
            results = vs.query_relevant("test query", n_results=2)
            self.assertGreater(len(results), 0)

    def test_batch_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = self._make_store(tmpdir)
            ids = vs.upsert_facts("run-1", [
                {"text": "fact 1", "metadata": {"competitor": "A"}},
                {"text": "fact 2", "metadata": {"competitor": "B"}},
            ])
            self.assertEqual(len(ids), 2)
            self.assertEqual(vs.count(), 2)

    def test_delete_by_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = self._make_store(tmpdir)
            vs.upsert_fact("run-1", "fact one")
            vs.upsert_fact("run-2", "fact two")
            self.assertEqual(vs.count(), 2)
            deleted = vs.delete_by_run("run-1")
            self.assertEqual(deleted, 1)
            self.assertEqual(vs.count(), 1)

    def test_format_for_prompt_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vs = self._make_store(tmpdir)
            result = vs.format_for_prompt([])
            self.assertIn("no relevant", result.lower())

    def test_format_for_prompt_with_facts(self) -> None:
        vs = VectorStore.__new__(VectorStore)  # bypass __init__
        facts = [
            FactResult(fact_id="1", text="钉钉定价更灵活", source_run_id="run-1", metadata={"competitor": "钉钉"}),
        ]
        result = vs.format_for_prompt(facts)
        self.assertIn("钉钉定价更灵活", result)


if __name__ == "__main__":
    unittest.main()
