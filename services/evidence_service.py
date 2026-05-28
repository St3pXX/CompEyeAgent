"""Service layer for indexing and querying source evidence."""

from __future__ import annotations

from collections.abc import Mapping

from models.source_layer import EvidenceItem, FetchStatus, SourceFetchEvent, SourceSeed
from services.evidence_extractor import extract_evidence
from services.source_connectors import SourceConnector, connector_for_provider
from storage.source_store import SQLiteSourceStore


DEFAULT_EVIDENCE_INDEX = (
    "Evidence Index: no indexed evidence is available for this request. "
    "Treat source coverage as sparse; use other credible sources instead of requiring every provider to match."
)


class EvidenceService:
    def __init__(self, store: SQLiteSourceStore, connectors: Mapping[str, SourceConnector] | None = None) -> None:
        self.store = store
        self.connectors = dict(connectors or {})

    def index_seed(self, seed: SourceSeed) -> list[EvidenceItem]:
        seed = self.store.upsert_seed(seed)
        if not seed.enabled:
            self.store.append_fetch_event(
                SourceFetchEvent(
                    seed_id=seed.seed_id,
                    provider=seed.provider,
                    url=seed.url,
                    status=FetchStatus.DISABLED,
                    message="Seed is disabled",
                )
            )
            return []

        connector = self.connectors.get(seed.provider.value) or connector_for_provider(seed.provider)
        try:
            documents = connector.fetch(seed)
        except Exception as exc:
            self.store.append_fetch_event(
                SourceFetchEvent(
                    seed_id=seed.seed_id,
                    provider=seed.provider,
                    url=seed.url,
                    status=FetchStatus.FAILED,
                    message=f"{type(exc).__name__}: {exc}",
                )
            )
            return []

        all_evidence: list[EvidenceItem] = []
        for document in documents:
            stored_document = self.store.upsert_document(document)
            evidence = extract_evidence(stored_document)
            self.store.replace_evidence(stored_document.document_id, evidence)
            all_evidence.extend(evidence)

        self.store.append_fetch_event(
            SourceFetchEvent(
                seed_id=seed.seed_id,
                provider=seed.provider,
                url=seed.url,
                status=FetchStatus.FETCHED,
                message=f"Fetched {len(documents)} documents and extracted {len(all_evidence)} evidence items",
            )
        )
        return all_evidence

    def query_evidence(self, competitor: str, dimensions: list[str]) -> list[EvidenceItem]:
        return self.store.query_evidence(competitor=competitor, dimensions=dimensions)

    def format_evidence_for_prompt(self, evidence_items: list[EvidenceItem]) -> str:
        if not evidence_items:
            return DEFAULT_EVIDENCE_INDEX
        lines = [
            "Evidence Index:",
            "Source coverage is expected to be sparse. Do not require every provider to contain every fact; synthesize credible evidence across available sources.",
        ]
        for item in evidence_items:
            lines.append(
                f"- competitor={item.competitor}; dimension={item.dimension}; "
                f"indicator={item.indicator}; confidence={item.confidence}; "
                f"provider={item.provider.value}; claim={item.claim}; "
                f"source={item.url}; snippet={item.snippet}"
            )
        return "\n".join(lines)
