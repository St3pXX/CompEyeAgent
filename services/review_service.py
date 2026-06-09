"""Human review queue service for CompEye Agent.

When a run completes with status ``needs_review``, the coordinator
automatically creates a review item.  The review queue API lets
reviewers approve, reject, or reassign items.

Integration points:
- ``coordinator_loop._persist_success()`` calls ``create_review_for_run()``
  when the run status is ``needs_review``.
- API endpoints in ``api_app.py`` expose CRUD + approve/reject operations.
"""

from __future__ import annotations

from models.schema import ReviewItem, ReviewStatus
from storage.protocols import RunStoreProtocol


class ReviewService:
    """Business logic for the human review queue."""

    def __init__(self, store: RunStoreProtocol) -> None:
        self.store = store

    def create_review_for_run(
        self,
        run_id: str,
        issues: list[str],
        *,
        assigned_to: str | None = None,
    ) -> ReviewItem:
        """Create a review item for a run that ended in needs_review.

        Idempotent: if a review already exists for this run, returns it.
        """
        existing = self.store.get_review_by_run(run_id)
        if existing is not None:
            return existing
        return self.store.create_review(run_id, issues, assigned_to=assigned_to)

    def list_reviews(
        self,
        *,
        status: ReviewStatus | None = None,
        run_id: str | None = None,
        limit: int = 50,
    ) -> list[ReviewItem]:
        return self.store.list_reviews(status=status, run_id=run_id, limit=limit)

    def get_review(self, review_id: str) -> ReviewItem:
        return self.store.get_review(review_id)

    def assign(self, review_id: str, assignee: str) -> ReviewItem:
        return self.store.update_review(review_id, status="in_review", assigned_to=assignee)

    def approve(self, review_id: str, notes: str | None = None) -> ReviewItem:
        return self.store.update_review(review_id, status="approved", review_notes=notes)

    def reject(self, review_id: str, notes: str | None = None) -> ReviewItem:
        return self.store.update_review(review_id, status="rejected", review_notes=notes)

    def add_notes(self, review_id: str, notes: str) -> ReviewItem:
        return self.store.update_review(review_id, review_notes=notes)
