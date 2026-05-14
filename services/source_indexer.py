"""Extract source references from generated reports."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel


URL_RE = re.compile(r"https?://[^\s<>\]\)\"'，。；;]+")
TRAILING_PUNCTUATION = ".,:!?)]}"
SnippetConfidence = Literal["high", "medium", "low"]


class ExtractedSource(BaseModel):
    uri: str
    snippet: str = ""
    confidence: SnippetConfidence = "medium"
    conclusion_id: str | None = None
    retrieved_at: str | None = None


def extract_source_references(report_markdown: str) -> list[ExtractedSource]:
    """Return unique URL references with nearby report context."""

    seen: set[str] = set()
    sources: list[ExtractedSource] = []
    for match in URL_RE.finditer(report_markdown):
        uri = _clean_uri(match.group(0))
        if not uri or uri in seen:
            continue
        seen.add(uri)
        sources.append(
            ExtractedSource(
                uri=uri,
                snippet=_snippet_around(report_markdown, match.start(), match.end()),
            )
        )
    return sources


def _clean_uri(uri: str) -> str:
    return uri.rstrip(TRAILING_PUNCTUATION)


def _snippet_around(text: str, start: int, end: int, *, max_length: int = 240) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    snippet = " ".join(text[line_start:line_end].strip().split())
    if len(snippet) <= max_length:
        return snippet

    prefix_budget = max((max_length - (end - start) - 5) // 2, 0)
    suffix_budget = max_length - (end - start) - prefix_budget - 5
    clipped_start = max(start - prefix_budget, line_start)
    clipped_end = min(end + suffix_budget, line_end)
    return "..." + " ".join(text[clipped_start:clipped_end].strip().split()) + "..."
