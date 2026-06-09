"""SQLite-backed run store for the Phase 1.5 product API."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models.schema import (
    AgentEvent,
    ArtifactKind,
    ArtifactRecord,
    CompetitorInput,
    EventType,
    ReviewItem,
    ReviewStatus,
    RunRecord,
    RunStatus,
    SourceRecord,
)


DEFAULT_DB_PATH = Path("data") / "run_store.sqlite3"
TERMINAL_STATUSES = {"passed", "needs_review", "failed", "cancelled"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteRunStore:
    """Small persistence adapter, intentionally replaceable by PostgreSQL later."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        configured_path = db_path or os.getenv("RUN_STORE_PATH") or DEFAULT_DB_PATH
        self.db_path = Path(configured_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def create_run(
        self,
        input_data: dict[str, Any],
        *,
        parent_run_id: str | None = None,
        status: RunStatus = "queued",
    ) -> RunRecord:
        now = utc_now()
        run_id = str(uuid.uuid4())
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO analysis_runs (
                    run_id, input_json, status, created_at, updated_at, completed_at, error, parent_run_id
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)
                """,
                (run_id, json.dumps(input_data, ensure_ascii=False), status, now, now, parent_run_id),
            )
        return self.get_run(run_id)

    def list_runs(self, limit: int = 50) -> list[RunRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM analysis_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._run_from_row(row) for row in rows]

    def get_run(self, run_id: str) -> RunRecord:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._run_from_row(row)

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
        completed: bool = False,
    ) -> RunRecord:
        now = utc_now()
        completed_at = now if completed or status in TERMINAL_STATUSES else None
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE analysis_runs
                SET status = ?, updated_at = ?, completed_at = COALESCE(?, completed_at), error = ?
                WHERE run_id = ?
                """,
                (status, now, completed_at, error, run_id),
            )
        return self.get_run(run_id)

    def append_event(
        self,
        run_id: str,
        event_type: EventType,
        message: str,
        *,
        agent: str | None = None,
        stage: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentEvent:
        now = utc_now()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_events (
                    run_id, type, agent, stage, message, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    event_type,
                    agent,
                    stage,
                    message,
                    json.dumps(payload or {}, ensure_ascii=False),
                    now,
                ),
            )
            event_id = int(cursor.lastrowid)
        return self.get_event(event_id)

    def get_event(self, event_id: int) -> AgentEvent:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM agent_events WHERE event_id = ?", (event_id,)).fetchone()
        if row is None:
            raise KeyError(str(event_id))
        return self._event_from_row(row)

    def list_events(self, run_id: str, *, after_event_id: int = 0) -> list[AgentEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM agent_events
                WHERE run_id = ? AND event_id > ?
                ORDER BY event_id ASC
                """,
                (run_id, after_event_id),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def create_artifact(self, run_id: str, kind: ArtifactKind, content: str) -> ArtifactRecord:
        now = utc_now()
        artifact_id = str(uuid.uuid4())
        preview = content[:600]
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, run_id, kind, content, content_preview, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, run_id, kind, content, preview, now),
            )
        return self.get_artifact(artifact_id)

    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM artifacts
                WHERE run_id = ?
                ORDER BY created_at ASC
                """,
                (run_id,),
            ).fetchall()
        return [self._artifact_from_row(row) for row in rows]

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return self._artifact_from_row(row)

    def list_sources(self, run_id: str) -> list[SourceRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM source_references
                WHERE run_id = ?
                ORDER BY rowid ASC
                """,
                (run_id,),
            ).fetchall()
        return [self._source_from_row(row) for row in rows]

    def create_sources(self, run_id: str, sources: list[Any]) -> list[SourceRecord]:
        if not sources:
            return []
        with self._connection() as conn:
            conn.executemany(
                """
                INSERT INTO source_references (
                    source_id, run_id, conclusion_id, uri, snippet, confidence, retrieved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(uuid.uuid4()),
                        run_id,
                        source.conclusion_id,
                        source.uri,
                        source.snippet,
                        source.confidence,
                        source.retrieved_at,
                    )
                    for source in sources
                ],
            )
        return self.list_sources(run_id)

    # ------------------------------------------------------------------
    # Review queue
    # ------------------------------------------------------------------

    def create_review(
        self,
        run_id: str,
        issues: list[str],
        *,
        assigned_to: str | None = None,
    ) -> ReviewItem:
        now = utc_now()
        review_id = str(uuid.uuid4())
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO review_queue (review_id, run_id, status, issues_json, assigned_to, created_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?, ?, ?)
                """,
                (review_id, run_id, json.dumps(issues, ensure_ascii=False), assigned_to, now, now),
            )
        return self.get_review(review_id)

    def get_review(self, review_id: str) -> ReviewItem:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM review_queue WHERE review_id = ?", (review_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Review {review_id} not found")
        return self._review_from_row(row)

    def list_reviews(
        self,
        *,
        status: ReviewStatus | None = None,
        run_id: str | None = None,
        limit: int = 50,
    ) -> list[ReviewItem]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if run_id:
            clauses.append("run_id = ?")
            params.append(run_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM review_queue {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._review_from_row(row) for row in rows]

    def update_review(
        self,
        review_id: str,
        *,
        status: ReviewStatus | None = None,
        assigned_to: str | None = None,
        review_notes: str | None = None,
    ) -> ReviewItem:
        sets: list[str] = ["updated_at = ?"]
        params: list[Any] = [utc_now()]
        if status is not None:
            sets.append("status = ?")
            params.append(status)
            if status in ("approved", "rejected"):
                sets.append("reviewed_at = ?")
                params.append(utc_now())
        if assigned_to is not None:
            sets.append("assigned_to = ?")
            params.append(assigned_to)
        if review_notes is not None:
            sets.append("review_notes = ?")
            params.append(review_notes)
        params.append(review_id)
        with self._connection() as conn:
            conn.execute(
                f"UPDATE review_queue SET {', '.join(sets)} WHERE review_id = ?",
                params,
            )
        return self.get_review(review_id)

    def get_review_by_run(self, run_id: str) -> ReviewItem | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM review_queue WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return self._review_from_row(row) if row else None

    def _review_from_row(self, row: sqlite3.Row) -> ReviewItem:
        return ReviewItem(
            review_id=row["review_id"],
            run_id=row["run_id"],
            status=row["status"],
            issues=json.loads(row["issues_json"]),
            assigned_to=row["assigned_to"],
            review_notes=row["review_notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            reviewed_at=row["reviewed_at"],
        )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_id TEXT PRIMARY KEY,
                    input_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    parent_run_id TEXT
                );

                CREATE TABLE IF NOT EXISTS agent_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    agent TEXT,
                    stage TEXT,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_agent_events_run_id_event_id
                ON agent_events(run_id, event_id);

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_preview TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_artifacts_run_id
                ON artifacts(run_id);

                CREATE TABLE IF NOT EXISTS source_references (
                    source_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    conclusion_id TEXT,
                    uri TEXT NOT NULL,
                    snippet TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    retrieved_at TEXT,
                    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_source_references_run_id
                ON source_references(run_id);

                CREATE TABLE IF NOT EXISTS review_queue (
                    review_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    issues_json TEXT NOT NULL DEFAULT '[]',
                    assigned_to TEXT,
                    review_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_review_queue_status
                ON review_queue(status);
                """
            )

    def _run_from_row(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            input=CompetitorInput(**json.loads(row["input_json"])),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            parent_run_id=row["parent_run_id"],
        )

    def _event_from_row(self, row: sqlite3.Row) -> AgentEvent:
        return AgentEvent(
            event_id=row["event_id"],
            run_id=row["run_id"],
            type=row["type"],
            agent=row["agent"],
            stage=row["stage"],
            message=row["message"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
        )

    def _artifact_from_row(self, row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row["artifact_id"],
            run_id=row["run_id"],
            kind=row["kind"],
            content=row["content"],
            content_preview=row["content_preview"],
            created_at=row["created_at"],
        )

    def _source_from_row(self, row: sqlite3.Row) -> SourceRecord:
        return SourceRecord(
            source_id=row["source_id"],
            run_id=row["run_id"],
            conclusion_id=row["conclusion_id"],
            uri=row["uri"],
            snippet=row["snippet"],
            confidence=row["confidence"],
            retrieved_at=row["retrieved_at"],
        )
