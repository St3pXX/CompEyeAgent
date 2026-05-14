import tempfile
import unittest
from pathlib import Path

from models.schema import CompetitorInput
from services.source_indexer import extract_source_references
from storage.run_store import SQLiteRunStore


class SourceIndexerTest(unittest.TestCase):
    def test_extracts_deduplicated_urls_with_context_snippets(self) -> None:
        report = """
        ## 竞品来源
        A 产品增长明显，参考 https://example.com/a?utm_source=test。

        另一段重复引用 https://example.com/a?utm_source=test 不应重复入库。
        价格策略参考：[官方说明](https://docs.example.cn/pricing)。
        """

        sources = extract_source_references(report)

        self.assertEqual([source.uri for source in sources], ["https://example.com/a?utm_source=test", "https://docs.example.cn/pricing"])
        self.assertIn("A 产品增长明显", sources[0].snippet)
        self.assertEqual(sources[0].confidence, "medium")

    def test_store_persists_extracted_sources_for_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            run = store.create_run(
                CompetitorInput(
                    productName="目标产品",
                    competitors=["竞品A"],
                    dimensions=[],
                ).model_dump()
            )
            sources = extract_source_references("证据来自 https://example.com/report。")

            stored = store.create_sources(run.run_id, sources)

            self.assertEqual(len(stored), 1)
            self.assertEqual(store.list_sources(run.run_id)[0].uri, "https://example.com/report")


if __name__ == "__main__":
    unittest.main()
