"""Deterministic evidence extraction from indexed source documents."""

from __future__ import annotations

from models.source_layer import EvidenceItem, RawDocument, SourceProvider


FREE_PLAN_KEYWORDS = ("免费套餐", "免费版", "免费", "Free plan", "free plan", "Free")
PRICING_HINTS = ("定价", "价格", "pricing", "price", "套餐")
PROVIDER_CONFIDENCE = {
    SourceProvider.OFFICIAL: "high",
    SourceProvider.FINANCE: "high",
    SourceProvider.PATENT: "high",
    SourceProvider.NEWS: "medium",
    SourceProvider.BLOG: "medium",
    SourceProvider.GITHUB: "medium",
    SourceProvider.SOCIAL: "low",
}


def extract_evidence(document: RawDocument) -> list[EvidenceItem]:
    text = " ".join(document.content.split())
    title = document.title or ""
    metadata_text = _metadata_text(document.metadata)
    url = document.url.lower()
    is_pricing = any(hint in title or hint in metadata_text or hint in url for hint in PRICING_HINTS)
    if not is_pricing:
        return _extract_metadata_hinted_evidence(document, text, title, metadata_text)

    free_match = _find_first(text, FREE_PLAN_KEYWORDS)
    if free_match < 0:
        return _extract_metadata_hinted_evidence(document, text, title, metadata_text)

    snippet = _snippet_around(text, free_match)
    return [
        EvidenceItem(
            document_id=document.document_id,
            provider=document.provider,
            competitor=document.competitor,
            dimension=str(document.metadata.get("dimension") or "定价"),
            indicator="免费套餐",
            claim=snippet,
            snippet=snippet,
            url=document.url,
            confidence=PROVIDER_CONFIDENCE.get(document.provider, "medium"),  # type: ignore[arg-type]
            metadata={"extractor": "keyword:v1"},
        )
    ]


def _extract_metadata_hinted_evidence(
    document: RawDocument,
    text: str,
    title: str,
    metadata_text: str,
) -> list[EvidenceItem]:
    dimension = document.metadata.get("dimension")
    indicators = document.metadata.get("indicators")
    if not dimension or not isinstance(indicators, list):
        return []

    haystack = " ".join([title, text, metadata_text])
    for indicator in indicators:
        keyword = str(indicator)
        match = haystack.find(keyword)
        if match < 0:
            continue
        snippet = _snippet_around(haystack, match)
        return [
            EvidenceItem(
                document_id=document.document_id,
                provider=document.provider,
                competitor=document.competitor,
                dimension=str(dimension),
                indicator=keyword,
                claim=snippet,
                snippet=snippet,
                url=document.url,
                confidence=PROVIDER_CONFIDENCE.get(document.provider, "medium"),  # type: ignore[arg-type]
                metadata={"extractor": "metadata-keyword:v1"},
            )
        ]
    return []


def _metadata_text(metadata: dict[str, object]) -> str:
    values: list[str] = []
    for value in metadata.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _find_first(text: str, keywords: tuple[str, ...]) -> int:
    positions = [text.find(keyword) for keyword in keywords if text.find(keyword) >= 0]
    return min(positions) if positions else -1


def _snippet_around(text: str, start: int, *, max_length: int = 240) -> str:
    half = max_length // 2
    left = max(start - half, 0)
    right = min(start + half, len(text))
    snippet = text[left:right].strip()
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    return snippet
