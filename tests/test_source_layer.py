import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

import api_app
from models.schema import CompetitorInput
from models.source_layer import EvidenceItem, FetchStatus, RawDocument, SourceFetchEvent, SourceSeed
from services.evidence_extractor import extract_evidence
from services.evidence_service import EvidenceService
from services.source_connectors import DisabledConnector, GitHubRepoConnector, NewsApiConnector, OfficialJinaConnector
from services.run_service import RunService
from storage.run_store import SQLiteRunStore
from storage.source_store import SQLiteSourceStore


class SourceLayerTest(unittest.TestCase):
    def test_store_upserts_seed_document_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteSourceStore(Path(tmpdir) / "sources.sqlite3")
            seed = store.upsert_seed(
                SourceSeed(
                    provider="official",
                    competitor="钉钉",
                    url="https://www.dingtalk.com/pricing",
                    label="定价页",
                )
            )
            document = store.upsert_document(
                RawDocument(
                    provider="official",
                    competitor=seed.competitor,
                    url=seed.url,
                    title=seed.label,
                    content="钉钉免费版提供基础协作能力。",
                )
            )
            duplicate = store.upsert_document(
                RawDocument(
                    provider="official",
                    competitor=seed.competitor,
                    url=seed.url,
                    title=seed.label,
                    content="钉钉免费版提供基础协作能力。",
                )
            )
            evidence = EvidenceItem(
                document_id=document.document_id,
                provider="official",
                competitor="钉钉",
                dimension="定价",
                indicator="免费套餐",
                claim="钉钉免费版提供基础协作能力。",
                snippet="钉钉免费版提供基础协作能力。",
                url=document.url,
                confidence="high",
            )

            store.replace_evidence(document.document_id, [evidence])
            store.append_fetch_event(
                SourceFetchEvent(
                    seed_id=seed.seed_id,
                    provider="official",
                    url=seed.url,
                    status=FetchStatus.FETCHED,
                    message="ok",
                )
            )

            self.assertEqual(len(store.list_seeds()), 1)
            self.assertEqual(document.document_id, duplicate.document_id)
            self.assertEqual(store.query_evidence(competitor="钉钉", dimensions=["定价"])[0].indicator, "免费套餐")
            self.assertEqual(store.list_fetch_events()[0].message, "ok")

    def test_extracts_official_free_plan_evidence(self) -> None:
        document = RawDocument(
            provider="official",
            competitor="钉钉",
            url="https://www.dingtalk.com/pricing",
            title="钉钉定价",
            content="钉钉免费版提供基础协作能力。专业版提供更多管理能力。",
        )

        evidence = extract_evidence(document)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].dimension, "定价")
        self.assertEqual(evidence[0].indicator, "免费套餐")
        self.assertEqual(evidence[0].confidence, "high")

    def test_official_jina_connector_parses_reader_content(self) -> None:
        response = Mock()
        response.text = "Title: 钉钉定价\n\n钉钉免费版提供基础协作能力。"
        response.raise_for_status.return_value = None
        client = Mock()
        client.get.return_value = response
        connector = OfficialJinaConnector(client=client, reader_base_url="https://r.jina.ai/http://")
        seed = SourceSeed(
            provider="official",
            competitor="钉钉",
            url="https://www.dingtalk.com/pricing",
            label="定价页",
        )

        documents = connector.fetch(seed)

        self.assertEqual(documents[0].title, "钉钉定价")
        self.assertIn("免费版", documents[0].content)
        client.get.assert_called_once_with("https://r.jina.ai/http://www.dingtalk.com/pricing")

    def test_disabled_connector_returns_no_documents(self) -> None:
        connector = DisabledConnector(provider="news", reason="NEWS_API_KEY missing")
        seed = SourceSeed(provider="news", competitor="钉钉", url="https://example.com/rss", label="news")

        self.assertEqual(connector.fetch(seed), [])

    def test_news_api_connector_maps_articles_to_raw_documents(self) -> None:
        response = Mock()
        response.json.return_value = {
            "articles": [
                {
                    "title": "钉钉发布 AI 产品",
                    "description": "钉钉发布新的协作能力。",
                    "content": "发布会介绍了新功能。",
                    "url": "https://news.example.com/dingtalk-ai",
                    "publishedAt": "2026-05-29T00:00:00Z",
                    "source": {"name": "Example News"},
                }
            ]
        }
        response.raise_for_status.return_value = None
        client = Mock()
        client.get.return_value = response
        connector = NewsApiConnector(client=client, api_key="test")
        seed = SourceSeed(
            provider="news",
            competitor="钉钉",
            url="newsapi://everything?query=钉钉",
            label="钉钉新闻",
            metadata={"dimension": "市场动态", "indicators": ["发布"]},
        )

        documents = connector.fetch(seed)

        self.assertEqual(documents[0].provider, "news")
        self.assertEqual(documents[0].url, "https://news.example.com/dingtalk-ai")
        self.assertIn("钉钉发布", documents[0].content)
        self.assertEqual(documents[0].metadata["source_name"], "Example News")

    def test_github_connector_maps_repo_metadata_to_raw_document(self) -> None:
        response = Mock()
        response.json.return_value = {
            "full_name": "owner/repo",
            "description": "Example repository",
            "stargazers_count": 42,
            "forks_count": 7,
            "open_issues_count": 3,
            "language": "Python",
            "updated_at": "2026-05-29T00:00:00Z",
            "created_at": "2025-01-01T00:00:00Z",
            "html_url": "https://github.com/owner/repo",
        }
        response.raise_for_status.return_value = None
        client = Mock()
        client.get.return_value = response
        connector = GitHubRepoConnector(client=client, token="")
        seed = SourceSeed(
            provider="github",
            competitor="开源产品",
            url="https://github.com/owner/repo",
            label="repo",
            metadata={"dimension": "开源", "indicators": ["stars"]},
        )

        documents = connector.fetch(seed)

        self.assertEqual(documents[0].provider, "github")
        self.assertIn("stars=42", documents[0].content)
        client.get.assert_called_once_with(
            "https://api.github.com/repos/owner/repo",
            headers={"Accept": "application/vnd.github+json"},
        )

    def test_metadata_hinted_evidence_extraction_supports_sparse_sources(self) -> None:
        document = RawDocument(
            provider="github",
            competitor="开源产品",
            url="https://github.com/owner/repo",
            title="owner/repo",
            content="repo=owner/repo; stars=42; forks=7; language=Python",
            metadata={"dimension": "开源", "indicators": ["stars"]},
        )

        evidence = extract_evidence(document)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].dimension, "开源")
        self.assertEqual(evidence[0].indicator, "stars")
        self.assertEqual(evidence[0].provider, "github")

    def test_evidence_service_indexes_seed_and_formats_prompt(self) -> None:
        class FakeConnector:
            provider = "official"

            def fetch(self, seed: SourceSeed) -> list[RawDocument]:
                return [
                    RawDocument(
                        provider="official",
                        competitor=seed.competitor,
                        url=seed.url,
                        title=seed.label,
                        content="钉钉免费版提供基础协作能力。",
                    )
                ]

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteSourceStore(Path(tmpdir) / "sources.sqlite3")
            service = EvidenceService(store=store, connectors={"official": FakeConnector()})
            evidence = service.index_seed(
                SourceSeed(
                    provider="official",
                    competitor="钉钉",
                    url="https://www.dingtalk.com/pricing",
                    label="钉钉定价",
                )
            )

            formatted = service.format_evidence_for_prompt(evidence)

            self.assertEqual(len(evidence), 1)
            self.assertIn("Source coverage is expected to be sparse", formatted)
            self.assertIn("钉钉", formatted)
            self.assertIn("https://www.dingtalk.com/pricing", formatted)

    def test_source_api_creates_seed_and_queries_empty_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_store = SQLiteSourceStore(Path(tmpdir) / "sources.sqlite3")
            api_app.source_store = source_store
            api_app.evidence_service = EvidenceService(source_store, connectors={})
            client = TestClient(api_app.app)

            response = client.post(
                "/api/sources/seeds",
                json={
                    "provider": "official",
                    "competitor": "钉钉",
                    "url": "https://www.dingtalk.com/pricing",
                    "label": "定价页",
                    "cadence": "daily",
                    "enabled": True,
                    "metadata": {},
                },
            )
            evidence_response = client.get("/api/sources/evidence?competitor=钉钉&dimension=定价")
            events_response = client.get("/api/sources/events")

            self.assertEqual(response.status_code, 201)
            self.assertEqual(client.get("/api/sources/seeds").json()["seeds"][0]["competitor"], "钉钉")
            self.assertEqual(evidence_response.json(), {"evidence": []})
            self.assertEqual(events_response.json(), {"events": []})

    def test_run_service_passes_default_evidence_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            service = RunService(store)
            run = service.create_run(
                CompetitorInput(
                    productName="目标产品",
                    competitors=["竞品A"],
                    dimensions=[{"name": "定价", "indicators": ["免费套餐"]}],
                )
            )
            result = SimpleNamespace(
                report="报告 [来源: https://example.com]\n\n## Provenance 索引",
                verifier_result='{"passed": true, "confidence": 95, "issues": []}',
                passed=True,
                retried=False,
            )
            run_analysis = Mock(return_value=result)
            fake_runner = SimpleNamespace(run_analysis=run_analysis)

            with unittest.mock.patch.dict(sys.modules, {"runner": fake_runner}):
                service.execute_run(run.run_id)

            called_inputs = run_analysis.call_args.args[0]
            self.assertIn("evidenceIndex", called_inputs)
            self.assertIn("Evidence Index", called_inputs["evidenceIndex"])
            self.assertIn("source coverage as sparse", called_inputs["evidenceIndex"])

    def test_run_service_injects_indexed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            source_store = SQLiteSourceStore(Path(tmpdir) / "sources.sqlite3")
            document = source_store.upsert_document(
                RawDocument(
                    provider="official",
                    competitor="钉钉",
                    url="https://www.dingtalk.com/pricing",
                    title="钉钉定价",
                    content="钉钉免费版提供基础协作能力。",
                )
            )
            source_store.replace_evidence(
                document.document_id,
                [
                    EvidenceItem(
                        document_id=document.document_id,
                        provider="official",
                        competitor="钉钉",
                        dimension="定价",
                        indicator="免费套餐",
                        claim="钉钉免费版提供基础协作能力。",
                        snippet="钉钉免费版提供基础协作能力。",
                        url=document.url,
                        confidence="high",
                    )
                ],
            )
            service = RunService(run_store, evidence_service=EvidenceService(source_store))
            run = service.create_run(
                CompetitorInput(
                    productName="飞书",
                    competitors=["钉钉"],
                    dimensions=[{"name": "定价", "indicators": ["免费套餐"]}],
                )
            )
            result = SimpleNamespace(
                report="报告 [来源: https://example.com]\n\n## Provenance 索引",
                verifier_result='{"passed": true, "confidence": 95, "issues": []}',
                passed=True,
                retried=False,
            )
            run_analysis = Mock(return_value=result)
            fake_runner = SimpleNamespace(run_analysis=run_analysis)

            with unittest.mock.patch.dict(sys.modules, {"runner": fake_runner}):
                service.execute_run(run.run_id)

            evidence_index = run_analysis.call_args.args[0]["evidenceIndex"]
            self.assertIn("钉钉免费版提供基础协作能力", evidence_index)
            self.assertIn("https://www.dingtalk.com/pricing", evidence_index)


if __name__ == "__main__":
    unittest.main()
