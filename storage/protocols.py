"""Protocol interfaces for storage backends.

Defines the contracts that SQLite, PostgreSQL, or any other storage
implementation must satisfy.  Consumers (RunService, CoordinatorLoopService,
etc.) depend on these Protocols rather than concrete classes, enabling
storage backend swaps without code changes.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from models.coordinator import DAGNode, ScratchpadItem
from models.schema import (
    AgentEvent,
    ArtifactRecord,
    EventType,
    RunRecord,
    RunStatus,
    SourceRecord,
)
from models.source_layer import (
    EvidenceItem,
    RawDocument,
    SourceFetchEvent,
    SourceSeed,
)


# ---------------------------------------------------------------------------
# Run Store
# ---------------------------------------------------------------------------

@runtime_checkable
class RunStoreProtocol(Protocol):
    """Persistence for runs, events, artifacts, and source references."""

    def create_run(
        self,
        input_data: dict[str, Any],
        *,
        parent_run_id: str | None = None,
        status: RunStatus = "queued",
    ) -> RunRecord: ...

    def list_runs(self, limit: int = 50) -> list[RunRecord]: ...

    def get_run(self, run_id: str) -> RunRecord: ...

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
        completed: bool = False,
    ) -> RunRecord: ...

    def append_event(
        self,
        run_id: str,
        event_type: EventType,
        message: str,
        *,
        agent: str | None = None,
        stage: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentEvent: ...

    def get_event(self, event_id: int) -> AgentEvent: ...

    def list_events(self, run_id: str, *, after_event_id: int = 0) -> list[AgentEvent]: ...

    def create_artifact(self, run_id: str, kind: str, content: str) -> ArtifactRecord: ...

    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...

    def get_artifact(self, artifact_id: str) -> ArtifactRecord: ...

    def list_sources(self, run_id: str) -> list[SourceRecord]: ...

    def create_sources(self, run_id: str, sources: list[Any]) -> list[SourceRecord]: ...


# ---------------------------------------------------------------------------
# Coordinator Store
# ---------------------------------------------------------------------------

@runtime_checkable
class CoordinatorStoreProtocol(Protocol):
    """Persistence for DAG nodes and scratchpad items."""

    def upsert_node(self, node: DAGNode) -> DAGNode: ...

    def get_node(self, run_id: str, key: str) -> DAGNode: ...

    def list_nodes(self, run_id: str) -> list[DAGNode]: ...

    def update_node_status(self, run_id: str, key: str, status: str) -> DAGNode: ...

    def update_node_refs(
        self,
        run_id: str,
        key: str,
        *,
        input_refs: list[str] | None = None,
        output_refs: list[str] | None = None,
    ) -> DAGNode: ...

    def update_node_metadata(self, run_id: str, key: str, metadata: dict[str, object]) -> DAGNode: ...

    def write_scratchpad_item(self, item: ScratchpadItem) -> ScratchpadItem: ...

    def get_scratchpad_item(self, run_id: str, path: str) -> ScratchpadItem: ...

    def list_scratchpad_items(self, run_id: str) -> list[ScratchpadItem]: ...


# ---------------------------------------------------------------------------
# Source Store
# ---------------------------------------------------------------------------

@runtime_checkable
class SourceStoreProtocol(Protocol):
    """Persistence for source seeds, documents, evidence, and fetch events."""

    def upsert_seed(self, seed: SourceSeed) -> SourceSeed: ...

    def get_seed(self, provider: str, competitor: str, url: str) -> SourceSeed: ...

    def list_seeds(self, *, enabled_only: bool = False) -> list[SourceSeed]: ...

    def upsert_document(self, document: RawDocument) -> RawDocument: ...

    def get_document(self, document_id: str) -> RawDocument: ...

    def list_documents(self) -> list[RawDocument]: ...

    def replace_evidence(self, document_id: str, items: list[EvidenceItem]) -> list[EvidenceItem]: ...

    def query_evidence(
        self,
        *,
        competitor: str | None = None,
        dimensions: list[str] | None = None,
        document_id: str | None = None,
    ) -> list[EvidenceItem]: ...

    def append_fetch_event(self, event: SourceFetchEvent) -> SourceFetchEvent: ...

    def list_fetch_events(self, limit: int = 100) -> list[SourceFetchEvent]: ...

    def latest_fetch_event(self, seed_id: str) -> SourceFetchEvent | None: ...
