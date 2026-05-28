"""SQLite-backed source intelligence store for Phase 2."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from models.source_layer import EvidenceItem, RawDocument, SourceFetchEvent, SourceSeed


DEFAULT_SOURCE_DB_PATH = Path("data") / "source_store.sqlite3"


class SQLiteSourceStore:
    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        configured_path = db_path or os.getenv("SOURCE_STORE_PATH") or DEFAULT_SOURCE_DB_PATH
        self.db_path = Path(configured_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def upsert_seed(self, seed: SourceSeed) -> SourceSeed:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO source_seeds (
                    seed_id, provider, competitor, url, label, cadence, enabled,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, competitor, url)
                DO UPDATE SET label = excluded.label,
                              cadence = excluded.cadence,
                              enabled = excluded.enabled,
                              metadata_json = excluded.metadata_json,
                              updated_at = excluded.updated_at
                """,
                (
                    seed.seed_id,
                    seed.provider.value,
                    seed.competitor,
                    seed.url,
                    seed.label,
                    seed.cadence.value,
                    int(seed.enabled),
                    json.dumps(seed.metadata, ensure_ascii=False),
                    seed.created_at,
                    seed.updated_at,
                ),
            )
        return self.get_seed(seed.provider.value, seed.competitor, seed.url)

    def get_seed(self, provider: str, competitor: str, url: str) -> SourceSeed:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM source_seeds WHERE provider = ? AND competitor = ? AND url = ?",
                (provider, competitor, url),
            ).fetchone()
        if row is None:
            raise KeyError(url)
        return self._seed_from_row(row)

    def list_seeds(self, *, enabled_only: bool = False) -> list[SourceSeed]:
        query = "SELECT * FROM source_seeds"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY competitor ASC, provider ASC, label ASC"
        with self._connection() as conn:
            rows = conn.execute(query).fetchall()
        return [self._seed_from_row(row) for row in rows]

    def upsert_document(self, document: RawDocument) -> RawDocument:
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT * FROM raw_documents WHERE provider = ? AND competitor = ? AND url = ?",
                (document.provider.value, document.competitor, document.url),
            ).fetchone()
            if existing and existing["content_hash"] == document.content_hash:
                conn.execute(
                    "UPDATE raw_documents SET fetched_at = ? WHERE document_id = ?",
                    (document.fetched_at, existing["document_id"]),
                )
                return self._document_from_row(existing)
            if existing:
                document.document_id = existing["document_id"]
                conn.execute(
                    """
                    UPDATE raw_documents
                    SET title = ?, content = ?, content_hash = ?, fetched_at = ?,
                        published_at = ?, metadata_json = ?
                    WHERE document_id = ?
                    """,
                    (
                        document.title,
                        document.content,
                        document.content_hash,
                        document.fetched_at,
                        document.published_at,
                        json.dumps(document.metadata, ensure_ascii=False),
                        document.document_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO raw_documents (
                        document_id, provider, competitor, url, title, content,
                        content_hash, fetched_at, published_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document.document_id,
                        document.provider.value,
                        document.competitor,
                        document.url,
                        document.title,
                        document.content,
                        document.content_hash,
                        document.fetched_at,
                        document.published_at,
                        json.dumps(document.metadata, ensure_ascii=False),
                    ),
                )
        return self.get_document(document.document_id)

    def get_document(self, document_id: str) -> RawDocument:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM raw_documents WHERE document_id = ?", (document_id,)).fetchone()
        if row is None:
            raise KeyError(document_id)
        return self._document_from_row(row)

    def list_documents(self) -> list[RawDocument]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM raw_documents ORDER BY fetched_at DESC").fetchall()
        return [self._document_from_row(row) for row in rows]

    def replace_evidence(self, document_id: str, items: list[EvidenceItem]) -> list[EvidenceItem]:
        with self._connection() as conn:
            conn.execute("DELETE FROM evidence_items WHERE document_id = ?", (document_id,))
            conn.executemany(
                """
                INSERT INTO evidence_items (
                    evidence_id, document_id, provider, competitor, dimension, indicator,
                    claim, snippet, url, confidence, observed_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.evidence_id,
                        item.document_id,
                        item.provider.value,
                        item.competitor,
                        item.dimension,
                        item.indicator,
                        item.claim,
                        item.snippet,
                        item.url,
                        item.confidence,
                        item.observed_at,
                        json.dumps(item.metadata, ensure_ascii=False),
                    )
                    for item in items
                ],
            )
        return self.query_evidence(document_id=document_id)

    def query_evidence(
        self,
        *,
        competitor: str | None = None,
        dimensions: list[str] | None = None,
        document_id: str | None = None,
    ) -> list[EvidenceItem]:
        clauses: list[str] = []
        params: list[object] = []
        if competitor:
            clauses.append("competitor = ?")
            params.append(competitor)
        if dimensions:
            placeholders = ",".join("?" for _ in dimensions)
            clauses.append(f"dimension IN ({placeholders})")
            params.extend(dimensions)
        if document_id:
            clauses.append("document_id = ?")
            params.append(document_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM evidence_items{where} ORDER BY observed_at DESC",
                tuple(params),
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def append_fetch_event(self, event: SourceFetchEvent) -> SourceFetchEvent:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO source_fetch_events (seed_id, provider, url, status, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.seed_id,
                    event.provider.value,
                    event.url,
                    event.status.value,
                    event.message,
                    event.created_at,
                ),
            )
            event.event_id = int(cursor.lastrowid)
        return event

    def list_fetch_events(self, limit: int = 100) -> list[SourceFetchEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM source_fetch_events
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._fetch_event_from_row(row) for row in rows]

    def latest_fetch_event(self, seed_id: str) -> SourceFetchEvent | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM source_fetch_events
                WHERE seed_id = ?
                ORDER BY event_id DESC
                LIMIT 1
                """,
                (seed_id,),
            ).fetchone()
        return self._fetch_event_from_row(row) if row else None

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
                CREATE TABLE IF NOT EXISTS source_seeds (
                    seed_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    competitor TEXT NOT NULL,
                    url TEXT NOT NULL,
                    label TEXT NOT NULL,
                    cadence TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(provider, competitor, url)
                );

                CREATE TABLE IF NOT EXISTS raw_documents (
                    document_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    competitor TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    published_at TEXT,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(provider, competitor, url)
                );

                CREATE TABLE IF NOT EXISTS evidence_items (
                    evidence_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    competitor TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    indicator TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    snippet TEXT NOT NULL,
                    url TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES raw_documents(document_id)
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_competitor_dimension
                ON evidence_items(competitor, dimension);

                CREATE TABLE IF NOT EXISTS source_fetch_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seed_id TEXT,
                    provider TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _seed_from_row(self, row: sqlite3.Row) -> SourceSeed:
        return SourceSeed(
            seed_id=row["seed_id"],
            provider=row["provider"],
            competitor=row["competitor"],
            url=row["url"],
            label=row["label"],
            cadence=row["cadence"],
            enabled=bool(row["enabled"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _document_from_row(self, row: sqlite3.Row) -> RawDocument:
        return RawDocument(
            document_id=row["document_id"],
            provider=row["provider"],
            competitor=row["competitor"],
            url=row["url"],
            title=row["title"],
            content=row["content"],
            content_hash=row["content_hash"],
            fetched_at=row["fetched_at"],
            published_at=row["published_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _evidence_from_row(self, row: sqlite3.Row) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=row["evidence_id"],
            document_id=row["document_id"],
            provider=row["provider"],
            competitor=row["competitor"],
            dimension=row["dimension"],
            indicator=row["indicator"],
            claim=row["claim"],
            snippet=row["snippet"],
            url=row["url"],
            confidence=row["confidence"],
            observed_at=row["observed_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _fetch_event_from_row(self, row: sqlite3.Row) -> SourceFetchEvent:
        return SourceFetchEvent(
            event_id=row["event_id"],
            seed_id=row["seed_id"],
            provider=row["provider"],
            url=row["url"],
            status=row["status"],
            message=row["message"],
            created_at=row["created_at"],
        )
