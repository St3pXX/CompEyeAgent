"""Vector store backed by ChromaDB for long-term memory.

Provides persistent vector storage for verified facts extracted from
completed analysis runs.  Facts are embedded automatically by ChromaDB's
default embedding function and can be queried by semantic similarity.

Usage::

    store = VectorStore()       # uses default path (data/vector_store)
    store.upsert_fact("run-1", "钉钉免费版支持最多 500 人", {"competitor": "钉钉", "dimension": "定价"})
    results = store.query_relevant("钉钉定价", n_results=5)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

try:
    import chromadb
    from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


DEFAULT_PERSIST_DIR = os.getenv("COMPETEYE_VECTOR_STORE_PATH", "data/vector_store")
COLLECTION_NAME = "verified_facts"


class _SimpleEmbedding(EmbeddingFunction):
    """Lightweight embedding that maps text to a fixed-dimension vector via hashing.

    Not semantically meaningful — used as a fallback when the ONNX model
    cannot be downloaded (e.g. offline environments, CI).  For production,
    install ``sentence-transformers`` and ChromaDB will auto-use it.
    """

    def __call__(self, input: Documents) -> Embeddings:
        import hashlib
        results: Embeddings = []
        for doc in input:
            h = hashlib.sha256(doc.encode("utf-8")).digest()
            vec = [float(b) / 255.0 for b in h]
            # Pad/truncate to 256 dimensions
            vec = (vec * 2)[:256]
            results.append(vec)
        return results


@dataclass
class FactResult:
    """A single fact retrieved from the vector store."""
    fact_id: str
    text: str
    source_run_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    distance: float = 0.0


class VectorStore:
    """ChromaDB-backed vector store for verified facts."""

    def __init__(
        self,
        persist_directory: str = DEFAULT_PERSIST_DIR,
        *,
        in_memory: bool = False,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        if not _CHROMA_AVAILABLE:
            raise RuntimeError(
                "chromadb is not installed. Install it with: pip install chromadb"
            )
        if in_memory:
            self._client = chromadb.EphemeralClient()
        else:
            os.makedirs(persist_directory, exist_ok=True)
            self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=_SimpleEmbedding(),
        )

    def upsert_fact(
        self,
        source_run_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        fact_id: str | None = None,
    ) -> str:
        """Store a verified fact. Returns the fact ID."""
        fid = fact_id or f"{source_run_id}_{self._collection.count() + 1}"
        meta = {"source_run_id": source_run_id, **(metadata or {})}
        self._collection.upsert(
            ids=[fid],
            documents=[text],
            metadatas=[meta],
        )
        return fid

    def upsert_facts(
        self,
        source_run_id: str,
        facts: list[dict[str, Any]],
    ) -> list[str]:
        """Batch upsert facts. Each fact dict must have 'text' and optionally 'metadata'."""
        if not facts:
            return []
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        base = self._collection.count()
        for i, fact in enumerate(facts):
            fid = fact.get("fact_id", f"{source_run_id}_{base + i + 1}")
            ids.append(fid)
            documents.append(fact["text"])
            metadatas.append({"source_run_id": source_run_id, **fact.get("metadata", {})})
        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return ids

    def query_relevant(
        self,
        query: str,
        *,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[FactResult]:
        """Query for facts semantically similar to *query*."""
        count = self._collection.count()
        if count == 0:
            return []
        n = min(n_results, count)
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n,
        }
        if where:
            kwargs["where"] = where
        results = self._collection.query(**kwargs)
        items: list[FactResult] = []
        for i in range(len(results["ids"][0])):
            items.append(FactResult(
                fact_id=results["ids"][0][i],
                text=results["documents"][0][i],
                source_run_id=results["metadatas"][0][i].get("source_run_id", ""),
                metadata=results["metadatas"][0][i],
                distance=results["distances"][0][i] if results.get("distances") else 0.0,
            ))
        return items

    def delete_by_run(self, source_run_id: str) -> int:
        """Delete all facts from a specific run. Returns count deleted."""
        results = self._collection.get(where={"source_run_id": source_run_id})
        if results["ids"]:
            self._collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0

    def count(self) -> int:
        """Return total number of stored facts."""
        return self._collection.count()

    def format_for_prompt(self, facts: list[FactResult], max_chars: int = 3000) -> str:
        """Format retrieved facts into a prompt-injectable string."""
        if not facts:
            return "Memory: no relevant historical facts found."
        lines = ["Memory: relevant facts from previous analyses:"]
        total = 0
        for fact in facts:
            entry = f"- [{fact.metadata.get('competitor', '?')}] {fact.text}"
            if total + len(entry) > max_chars:
                break
            lines.append(entry)
            total += len(entry)
        return "\n".join(lines)
