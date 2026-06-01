"""SQLite-backed DAG and scratchpad store for Phase 2 Coordinator Foundation."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from models.coordinator import DAGNode, ScratchpadItem, utc_now


DEFAULT_COORDINATOR_DB_PATH = Path("data") / "coordinator_store.sqlite3"


class SQLiteCoordinatorStore:
    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        configured_path = db_path or os.getenv("COORDINATOR_STORE_PATH") or DEFAULT_COORDINATOR_DB_PATH
        self.db_path = Path(configured_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def upsert_node(self, node: DAGNode) -> DAGNode:
        node.updated_at = utc_now()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO dag_nodes (
                    node_id, run_id, key, name, agent, status, depends_on_json,
                    input_refs_json, output_refs_json, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, key)
                DO UPDATE SET name = excluded.name,
                              agent = excluded.agent,
                              status = excluded.status,
                              depends_on_json = excluded.depends_on_json,
                              input_refs_json = excluded.input_refs_json,
                              output_refs_json = excluded.output_refs_json,
                              metadata_json = excluded.metadata_json,
                              updated_at = excluded.updated_at
                """,
                (
                    node.node_id,
                    node.run_id,
                    node.key,
                    node.name,
                    node.agent,
                    node.status,
                    json.dumps(node.depends_on, ensure_ascii=False),
                    json.dumps(node.input_refs, ensure_ascii=False),
                    json.dumps(node.output_refs, ensure_ascii=False),
                    json.dumps(node.metadata, ensure_ascii=False),
                    node.created_at,
                    node.updated_at,
                ),
            )
        return self.get_node(node.run_id, node.key)

    def get_node(self, run_id: str, key: str) -> DAGNode:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM dag_nodes WHERE run_id = ? AND key = ?", (run_id, key)).fetchone()
        if row is None:
            raise KeyError(key)
        return self._node_from_row(row)

    def list_nodes(self, run_id: str) -> list[DAGNode]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM dag_nodes
                WHERE run_id = ?
                ORDER BY rowid ASC
                """,
                (run_id,),
            ).fetchall()
        return [self._node_from_row(row) for row in rows]

    def update_node_status(self, run_id: str, key: str, status: str) -> DAGNode:
        now = utc_now()
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM dag_nodes WHERE run_id = ? AND key = ?", (run_id, key)).fetchone()
            if row is None:
                raise KeyError(key)
            conn.execute(
                """
                UPDATE dag_nodes
                SET status = ?, updated_at = ?
                WHERE run_id = ? AND key = ?
                """,
                (status, now, run_id, key),
            )
        return self.get_node(run_id, key)

    def update_node_refs(
        self,
        run_id: str,
        key: str,
        *,
        input_refs: list[str] | None = None,
        output_refs: list[str] | None = None,
    ) -> DAGNode:
        node = self.get_node(run_id, key)
        next_input_refs = node.input_refs if input_refs is None else input_refs
        next_output_refs = node.output_refs if output_refs is None else output_refs
        now = utc_now()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE dag_nodes
                SET input_refs_json = ?, output_refs_json = ?, updated_at = ?
                WHERE run_id = ? AND key = ?
                """,
                (
                    json.dumps(next_input_refs, ensure_ascii=False),
                    json.dumps(next_output_refs, ensure_ascii=False),
                    now,
                    run_id,
                    key,
                ),
            )
        return self.get_node(run_id, key)

    def update_node_metadata(self, run_id: str, key: str, metadata: dict[str, object]) -> DAGNode:
        now = utc_now()
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM dag_nodes WHERE run_id = ? AND key = ?", (run_id, key)).fetchone()
            if row is None:
                raise KeyError(key)
            current = json.loads(row["metadata_json"])
            current.update(metadata)
            conn.execute(
                """
                UPDATE dag_nodes
                SET metadata_json = ?, updated_at = ?
                WHERE run_id = ? AND key = ?
                """,
                (json.dumps(current, ensure_ascii=False), now, run_id, key),
            )
        return self.get_node(run_id, key)

    def write_scratchpad_item(self, item: ScratchpadItem) -> ScratchpadItem:
        item.content_preview = item.content[:600]
        item.updated_at = utc_now()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO scratchpad_items (
                    item_id, run_id, path, kind, content, content_preview,
                    producer_node_id, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, path)
                DO UPDATE SET kind = excluded.kind,
                              content = excluded.content,
                              content_preview = excluded.content_preview,
                              producer_node_id = excluded.producer_node_id,
                              metadata_json = excluded.metadata_json,
                              updated_at = excluded.updated_at
                """,
                (
                    item.item_id,
                    item.run_id,
                    item.path,
                    item.kind,
                    item.content,
                    item.content_preview,
                    item.producer_node_id,
                    json.dumps(item.metadata, ensure_ascii=False),
                    item.created_at,
                    item.updated_at,
                ),
            )
        return self.get_scratchpad_item(item.run_id, item.path)

    def get_scratchpad_item(self, run_id: str, path: str) -> ScratchpadItem:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM scratchpad_items WHERE run_id = ? AND path = ?", (run_id, path)).fetchone()
        if row is None:
            raise KeyError(path)
        return self._scratchpad_from_row(row)

    def list_scratchpad_items(self, run_id: str) -> list[ScratchpadItem]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scratchpad_items
                WHERE run_id = ?
                ORDER BY path ASC
                """,
                (run_id,),
            ).fetchall()
        return [self._scratchpad_from_row(row) for row in rows]

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
                CREATE TABLE IF NOT EXISTS dag_nodes (
                    node_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    depends_on_json TEXT NOT NULL,
                    input_refs_json TEXT NOT NULL,
                    output_refs_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(run_id, key)
                );

                CREATE INDEX IF NOT EXISTS idx_dag_nodes_run_id
                ON dag_nodes(run_id);

                CREATE TABLE IF NOT EXISTS scratchpad_items (
                    item_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_preview TEXT NOT NULL,
                    producer_node_id TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(run_id, path)
                );

                CREATE INDEX IF NOT EXISTS idx_scratchpad_items_run_id
                ON scratchpad_items(run_id);
                """
            )

    def _node_from_row(self, row: sqlite3.Row) -> DAGNode:
        return DAGNode(
            node_id=row["node_id"],
            run_id=row["run_id"],
            key=row["key"],
            name=row["name"],
            agent=row["agent"],
            status=row["status"],
            depends_on=json.loads(row["depends_on_json"]),
            input_refs=json.loads(row["input_refs_json"]),
            output_refs=json.loads(row["output_refs_json"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _scratchpad_from_row(self, row: sqlite3.Row) -> ScratchpadItem:
        return ScratchpadItem(
            item_id=row["item_id"],
            run_id=row["run_id"],
            path=row["path"],
            kind=row["kind"],
            content=row["content"],
            content_preview=row["content_preview"],
            producer_node_id=row["producer_node_id"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
