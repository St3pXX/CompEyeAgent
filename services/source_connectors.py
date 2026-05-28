"""Source connectors for Phase 2 source intelligence."""

from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse
from typing import Protocol

import httpx

from models.source_layer import RawDocument, SourceProvider, SourceSeed


class SourceConnector(Protocol):
    provider: SourceProvider

    def fetch(self, seed: SourceSeed) -> list[RawDocument]:
        ...


class OfficialJinaConnector:
    provider = SourceProvider.OFFICIAL

    def __init__(self, client: httpx.Client | None = None, reader_base_url: str | None = None) -> None:
        self.client = client or httpx.Client(timeout=30)
        self.reader_base_url = reader_base_url or os.getenv("JINA_READER_BASE_URL", "https://r.jina.ai/http://")

    def fetch(self, seed: SourceSeed) -> list[RawDocument]:
        response = self.client.get(self._reader_url(seed.url))
        response.raise_for_status()
        title, content = _parse_jina_response(response.text)
        return [
            RawDocument(
                provider=SourceProvider.OFFICIAL,
                competitor=seed.competitor,
                url=seed.url,
                title=title or seed.label,
                content=content,
                metadata={
                    "seed_id": seed.seed_id,
                    "seed_label": seed.label,
                    "connector": "jina_reader",
                    **seed.metadata,
                },
            )
        ]

    def _reader_url(self, url: str) -> str:
        if url.startswith("https://"):
            return f"{self.reader_base_url}{url.removeprefix('https://')}"
        if url.startswith("http://"):
            return f"{self.reader_base_url}{url.removeprefix('http://')}"
        return f"{self.reader_base_url}https://{url}"


class NewsApiConnector:
    provider = SourceProvider.NEWS

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None) -> None:
        self.client = client or httpx.Client(timeout=30)
        self.api_key = api_key or os.getenv("NEWS_API_KEY", "")

    def fetch(self, seed: SourceSeed) -> list[RawDocument]:
        if not self.api_key:
            return []
        query = str(seed.metadata.get("query") or _query_from_url(seed.url) or seed.competitor)
        response = self.client.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": seed.metadata.get("language", "zh"),
                "sortBy": seed.metadata.get("sortBy", "publishedAt"),
                "pageSize": int(seed.metadata.get("pageSize", 5)),
                "apiKey": self.api_key,
            },
        )
        response.raise_for_status()
        articles = response.json().get("articles", [])
        documents: list[RawDocument] = []
        for article in articles:
            url = article.get("url") or seed.url
            title = article.get("title") or seed.label
            description = article.get("description") or ""
            content = article.get("content") or ""
            source_name = (article.get("source") or {}).get("name", "")
            documents.append(
                RawDocument(
                    provider=SourceProvider.NEWS,
                    competitor=seed.competitor,
                    url=url,
                    title=title,
                    content="\n".join(part for part in [title, description, content] if part),
                    published_at=article.get("publishedAt"),
                    metadata={
                        "seed_id": seed.seed_id,
                        "seed_label": seed.label,
                        "connector": "newsapi",
                        "source_name": source_name,
                        **seed.metadata,
                    },
                )
            )
        return documents


class GitHubRepoConnector:
    provider = SourceProvider.GITHUB

    def __init__(self, client: httpx.Client | None = None, token: str | None = None) -> None:
        self.client = client or httpx.Client(timeout=30)
        self.token = token or os.getenv("GITHUB_TOKEN", "")

    def fetch(self, seed: SourceSeed) -> list[RawDocument]:
        owner, repo = _github_repo_from_url(seed.url)
        if not owner or not repo:
            return []
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = self.client.get(api_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        title = payload.get("full_name") or seed.label
        content = (
            f"repo={payload.get('full_name', '')}; "
            f"description={payload.get('description') or ''}; "
            f"stars={payload.get('stargazers_count', 0)}; "
            f"forks={payload.get('forks_count', 0)}; "
            f"open_issues={payload.get('open_issues_count', 0)}; "
            f"language={payload.get('language') or ''}; "
            f"updated_at={payload.get('updated_at') or ''}"
        )
        return [
            RawDocument(
                provider=SourceProvider.GITHUB,
                competitor=seed.competitor,
                url=payload.get("html_url") or seed.url,
                title=title,
                content=content,
                published_at=payload.get("created_at"),
                metadata={
                    "seed_id": seed.seed_id,
                    "seed_label": seed.label,
                    "connector": "github_repo",
                    **seed.metadata,
                },
            )
        ]


class DisabledConnector:
    def __init__(self, provider: SourceProvider | str, reason: str) -> None:
        self.provider = SourceProvider(provider)
        self.reason = reason

    def fetch(self, seed: SourceSeed) -> list[RawDocument]:
        return []


def connector_for_provider(provider: SourceProvider | str) -> SourceConnector:
    provider = SourceProvider(provider)
    if provider == SourceProvider.OFFICIAL:
        return OfficialJinaConnector()
    if provider == SourceProvider.NEWS:
        if os.getenv("NEWS_API_KEY"):
            return NewsApiConnector()
        return DisabledConnector(provider, "NEWS_API_KEY is not configured")
    if provider == SourceProvider.GITHUB:
        return GitHubRepoConnector()
    return DisabledConnector(provider, f"{provider.value} connector is not implemented in Phase 2 source-layer v1")


def _parse_jina_response(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    title = ""
    if lines and lines[0].startswith("Title:"):
        title = lines[0].removeprefix("Title:").strip()
        content = "\n".join(lines[1:]).strip()
    else:
        content = text.strip()
    return title, content


def _query_from_url(url: str) -> str:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("query") or parse_qs(parsed.query).get("q")
    return values[0] if values else ""


def _github_repo_from_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.netloc == "api.github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 3 and parts[0] == "repos":
            return parts[1], parts[2]
    if parsed.netloc.endswith("github.com"):
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            return parts[0], parts[1]
    return "", ""
