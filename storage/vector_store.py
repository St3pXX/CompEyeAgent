"""Vector store backed by ChromaDB for long-term memory.

Provides persistent vector storage for verified facts extracted from
completed analysis runs.  Facts are embedded via FastEmbed (ONNX, lightweight,
no PyTorch dependency) and can be queried by semantic similarity.

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

# FastEmbed ONNX model — ~33MB model, ~50MB runtime, no PyTorch/CUDA.
# bge-small-zh-v1.5: 512-dim, Chinese-optimized, fast on CPU.
DEFAULT_EMBEDDING_MODEL = os.getenv("COMPETEYE_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")


class _FastEmbedBge(EmbeddingFunction):
    """FastEmbed ONNX embedding (default: BAAI/bge-small-zh-v1.5, 512-dim).

    ~50MB ONNX Runtime + ~33MB model — no PyTorch, no CUDA, runs fast on CPU.
    Free, on-prem, data never leaves the host.
    """

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        vectors = self._model.embed(list(input))
        return [vec.tolist() for vec in vectors]


class _SimpleEmbedding(EmbeddingFunction):
    """Deterministic hash embedding — NOT semantically meaningful.

    Fallback only, for environments where ``fastembed`` is unavailable.
    Produces 512-dim vectors to match bge-small-zh-v1.5 so the ChromaDB
    collection stays compatible either way.
    """

    def __call__(self, input: Documents) -> Embeddings:
        import hashlib
        results: Embeddings = []
        for doc in input:
            h = hashlib.sha256(doc.encode("utf-8")).digest()  # 32 bytes
            vec = [float(b) / 255.0 for b in h]
            # Tile to 512 (bge-small-zh-v1.5 dimension).
            vec = (vec * 16)[:512]
            results.append(vec)
        return results


def _build_embedding_function(model_name: str = DEFAULT_EMBEDDING_MODEL) -> EmbeddingFunction:
    """Return the FastEmbed bge embedding if available, else hash fallback."""
    try:
        return _FastEmbedBge(model_name)
    except Exception:
        return _SimpleEmbedding()


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
        self._embedding_function = _build_embedding_function()
        self._collection = self._get_or_rebuild_collection(collection_name)

    def _get_or_rebuild_collection(self, collection_name: str):
        """Get the collection, rebuilding it if the embedding dimension changed.

        The legacy hash embedding was 256-dim; current FastEmbed model is
        512-dim.  An old persisted collection would raise a dimension-mismatch
        on query, so if an incompatible collection exists we drop and recreate
        it.  The only data lost is previous hash vectors — no semantic loss.
        """
        collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding_function,
        )
        try:
            if collection.count() > 0:
                collection.query(query_texts=["probe"], n_results=1)
        except Exception:
            self._client.delete_collection(collection_name)
            collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embedding_function,
            )
        return collection

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
