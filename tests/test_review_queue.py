"""Tests for the review queue — storage, service, and API endpoints."""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import api_app
from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from services.run_service import RunService
from storage.coordinator_store import SQLiteCoordinatorStore
from storage.run_store import SQLiteRunStore


class ReviewStoreTest(unittest.TestCase):
    def test_create_and_get_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            run = store.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump())

            review = store.create_review(run.run_id, ["缺少定价数据", "来源不足"])

            self.assertEqual(review.run_id, run.run_id)
            self.assertEqual(review.status, "pending")
            self.assertEqual(review.issues, ["缺少定价数据", "来源不足"])
            self.assertIsNone(review.assigned_to)

            fetched = store.get_review(review.review_id)
            self.assertEqual(fetched.review_id, review.review_id)

    def test_list_reviews_filters_by_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            run = store.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump())
            store.create_review(run.run_id, ["issue"])

            pending = store.list_reviews(status="pending")
            self.assertEqual(len(pending), 1)

            approved = store.list_reviews(status="approved")
            self.assertEqual(len(approved), 0)

    def test_update_review_approve(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            run = store.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump())
            review = store.create_review(run.run_id, ["issue"])

            updated = store.update_review(review.review_id, status="approved", review_notes="Looks good")

            self.assertEqual(updated.status, "approved")
            self.assertEqual(updated.review_notes, "Looks good")
            self.assertIsNotNone(updated.reviewed_at)

    def test_update_review_assign(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            run = store.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump())
            review = store.create_review(run.run_id, ["issue"])

            updated = store.update_review(review.review_id, status="in_review", assigned_to="alice")

            self.assertEqual(updated.status, "in_review")
            self.assertEqual(updated.assigned_to, "alice")

    def test_get_review_by_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            run = store.create_run(CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump())
            store.create_review(run.run_id, ["issue"])

            found = store.get_review_by_run(run.run_id)
            self.assertIsNotNone(found)
            self.assertEqual(found.run_id, run.run_id)

            not_found = store.get_review_by_run("nonexistent")
            self.assertIsNone(not_found)

    def test_get_review_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            with self.assertRaises(KeyError):
                store.get_review("nonexistent")


class ReviewApiTest(unittest.TestCase):
    def test_review_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            coordinator_store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            coordinator_service = CoordinatorFoundationService(coordinator_store)
            api_app.store = run_store
            api_app.coordinator_store = coordinator_store
            api_app.coordinator_service = coordinator_service
            client = TestClient(api_app.app)

            run = run_store.create_run(
                CompetitorInput(productName="飞书", competitors=["钉钉"], dimensions=[]).model_dump()
            )
            run_store.create_review(run.run_id, ["缺少定价数据"])

            # List reviews
            resp = client.get("/api/reviews")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(len(resp.json()["reviews"]), 1)

            # Get review by run
            resp = client.get(f"/api/runs/{run.run_id}/review")
            self.assertEqual(resp.status_code, 200)
            review_id = resp.json()["review"]["review_id"]

            # Get single review
            resp = client.get(f"/api/reviews/{review_id}")
            self.assertEqual(resp.status_code, 200)

            # Assign
            resp = client.post(f"/api/reviews/{review_id}/assign", json={"assignee": "alice"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["review"]["assigned_to"], "alice")

            # Approve
            resp = client.post(f"/api/reviews/{review_id}/approve", json={"notes": "LGTM"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["review"]["status"], "approved")

            # 404 for nonexistent
            resp = client.get("/api/reviews/nonexistent")
            self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
