"""Long-term memory service for CompEye Agent.

Extracts verified facts from completed analysis runs and stores them in a
vector database for cross-run retrieval.  When a new run starts, the
Collector and Analyzer agents can query historical facts to avoid
re-collecting already-verified information.

Usage::

    memory = MemoryService(vector_store, run_store)
    memory.ingest_completed_run("run-1")          # extract & store facts
    context = memory.query_for_run(competitors, dimensions)  # get relevant facts
"""

from __future__ import annotations

import json
import re
from typing import Any

from models.schema import CompetitorInput
from storage.protocols import RunStoreProtocol
from storage.vector_store import FactResult, VectorStore


class MemoryService:
    """Extracts facts from completed runs and provides cross-run retrieval."""

    def __init__(self, vector_store: VectorStore, run_store: RunStoreProtocol) -> None:
        self.vector = vector_store
        self.run_store = run_store

    def ingest_completed_run(self, run_id: str) -> int:
        """Extract verified facts from a completed run and store them.

        Returns the number of facts extracted and stored.
        """
        try:
            run = self.run_store.get_run(run_id)
        except KeyError:
            return 0

        if run.status not in ("passed", "needs_review"):
            return 0

        facts = self._extract_facts_from_report(run_id)
        if not facts:
            return 0

        self.vector.upsert_facts(run_id, facts)
        return len(facts)

    def query_for_run(
        self,
        competitors: list[str],
        dimensions: list[str],
        *,
        n_results: int = 10,
    ) -> str:
        """Query memory for facts relevant to the given competitors and dimensions.

        Returns a formatted string suitable for injection into agent prompts.
        """
        queries = []
        for competitor in competitors:
            for dimension in dimensions:
                queries.append(f"{competitor} {dimension}")
            queries.append(competitor)

        all_facts: list[FactResult] = []
        seen_ids: set[str] = set()
        for query in queries:
            results = self.vector.query_relevant(query, n_results=n_results)
            for fact in results:
                if fact.fact_id not in seen_ids:
                    seen_ids.add(fact.fact_id)
                    all_facts.append(fact)

        # Sort by relevance (lower distance = more relevant)
        all_facts.sort(key=lambda f: f.distance)
        return self.vector.format_for_prompt(all_facts[:n_results])

    def query_raw(
        self,
        query: str,
        *,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[FactResult]:
        """Direct semantic query against the vector store."""
        return self.vector.query_relevant(query, n_results=n_results, where=where)

    def _extract_facts_from_report(self, run_id: str) -> list[dict[str, Any]]:
        """Extract claim-like facts from the report and source references."""
        facts: list[dict[str, Any]] = []

        # Get the report artifact
        try:
            artifacts = self.run_store.list_artifacts(run_id)
        except Exception:
            return facts

        report_md = ""
        verifier_json = ""
        for art in artifacts:
            if art.kind == "report_markdown":
                report_md = art.content
            elif art.kind == "verifier_json":
                verifier_json = art.content

        # Only ingest if verifier passed or confidence >= 70
        if not self._is_verified(verifier_json):
            return facts

        # Extract source references
        sources = self.run_store.list_sources(run_id)
        source_map: dict[str, str] = {}
        for src in sources:
            source_map[src.uri] = src.snippet

        # Extract claim-like lines from the report
        run = self.run_store.get_run(run_id)
        competitors = [run.input.productName, *run.input.competitors]

        for line in report_md.splitlines():
            line = line.strip()
            if not line or len(line) < 20:
                continue
            if re.match(r"^#{1,6}\s+", line) or "|" in line:
                continue
            if not re.match(r"^([-*]|\d+[.)])\s+", line):
                continue

            # Find source URLs in the line
            urls = re.findall(r"https?://[^\s\])>，。；,]+", line)
            # Clean the line for storage
            clean = re.sub(r"\[来源:\s*[^\]]+\]", "", line).strip()
            clean = re.sub(r"https?://[^\s]+", "", clean).strip()

            if clean and len(clean) >= 10:
                # Determine which competitor this is about
                competitor = next(
                    (c for c in competitors if c in clean),
                    competitors[0] if competitors else "unknown",
                )
                facts.append({
                    "text": clean,
                    "metadata": {
                        "competitor": competitor,
                        "source_urls": ", ".join(urls[:3]) if urls else "",
                        "run_id": run_id,
                    },
                })

        return facts

    def _is_verified(self, verifier_json: str) -> bool:
        """Check if the verifier result indicates acceptable quality."""
        if not verifier_json:
            return False
        try:
            data = json.loads(verifier_json)
            confidence = data.get("confidence", 0)
            return isinstance(confidence, (int, float)) and confidence >= 70
        except (json.JSONDecodeError, AttributeError):
            return False

    def format_memory_for_prompt(
        self,
        competitors: list[str],
        dimensions: list[str],
    ) -> str:
        """Convenience method: query and format in one call."""
        return self.query_for_run(competitors, dimensions)
