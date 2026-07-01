"""Tests for the bge-based semantic embedding in storage.vector_store.

The semantic-quality test requires the local sentence-transformers model; it is
skipped when unavailable (offline CI) so the suite stays green.  The fallback
dimension test always runs.
"""

from __future__ import annotations

import unittest
import uuid

from storage.vector_store import (
    _SimpleEmbedding,
    _build_embedding_function,
    _BgeEmbedding,
    VectorStore,
)


def _sentence_transformers_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


class FallbackEmbeddingTest(unittest.TestCase):
    """The hash fallback must be 768-dim to stay collection-compatible with bge."""

    def test_fallback_dimension_is_768(self):
        emb = _SimpleEmbedding()
        vectors = emb(["测试文本", "another"])
        self.assertEqual(len(vectors[0]), 768)
        self.assertEqual(len(vectors[1]), 768)


@unittest.skipUnless(
    _sentence_transformers_available(),
    "sentence-transformers not installed",
)
class BgeSemanticTest(unittest.TestCase):
    """bge embeddings must make semantically related text closer than unrelated."""

    @classmethod
    def setUpClass(cls):
        # Load once; model download may take a while on first run.
        cls.emb = _BgeEmbedding()

    def _cosine(self, a, b):
        # vectors are already normalized, so dot product == cosine similarity
        return sum(x * y for x, y in zip(a, b))

    def test_related_closer_than_unrelated(self):
        vecs = self.emb([
            "钉钉的定价方案和免费套餐",   # anchor
            "钉钉免费版支持多少人使用",   # related (same topic: 钉钉 pricing)
            "今天北京的天气非常晴朗",     # unrelated
        ])
        sim_related = self._cosine(vecs[0], vecs[1])
        sim_unrelated = self._cosine(vecs[0], vecs[2])
        self.assertGreater(sim_related, sim_unrelated)

    def test_dimension_is_768(self):
        vecs = self.emb(["测试"])
        self.assertEqual(len(vecs[0]), 768)

    def test_store_semantic_retrieval(self):
        vs = VectorStore(in_memory=True, collection_name=f"test_{uuid.uuid4().hex[:8]}")
        vs.upsert_fact("run-1", "钉钉免费版最多支持 500 人", {"competitor": "钉钉"})
        vs.upsert_fact("run-1", "飞书的视频会议功能很强大", {"competitor": "飞书"})
        results = vs.query_relevant("钉钉的定价和人数限制", n_results=1)
        self.assertEqual(len(results), 1)
        # The 钉钉 pricing fact should win over the 飞书 video fact.
        self.assertIn("钉钉", results[0].text)


if __name__ == "__main__":
    unittest.main()
