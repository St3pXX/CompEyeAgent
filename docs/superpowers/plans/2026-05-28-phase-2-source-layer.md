# Phase 2 Source Layer Sub-Milestone Implementation Plan

## Goal

Build the Source Layer sub-milestone inside Phase 2 before the CrewAI analysis chain. This is not the full Phase 2 roadmap. The layer indexes credible but sparse evidence from official pages, news, GitHub, blogs/RSS, and Reddit social search, while keeping finance and patent behind explicit disabled boundaries. The Collector should synthesize across whatever credible sources are available instead of requiring every provider to cover every fact.

## Current Scope

- Add source-layer data models for seeds, raw documents, evidence items, and fetch events.
- Add SQLite persistence for source seeds, raw documents, extracted evidence, and fetch history.
- Add official source ingestion through Jina Reader.
- Add NewsAPI ingestion when `NEWS_API_KEY` is configured.
- Add GitHub public repository metadata ingestion, with optional `GITHUB_TOKEN` for rate limits.
- Add RSS/Atom blog ingestion without API keys.
- Add Reddit public search ingestion as a lightweight social signal, with documented 403/rate-limit caveats.
- Keep finance and patent providers behind stable disabled connector boundaries until their API policies are ready.
- Inject an Evidence Index into the existing Collector prompt before runtime web search.
- Provide local CLI operations for initializing default seeds and indexing due sources.

## Design Principles

- Source coverage is sparse by design.
- Missing coverage from one provider is not a failure.
- Unsupported claims are gaps; missing provider categories are not.
- Prefer official, finance, and patent evidence when directly relevant.
- Use news, blogs, GitHub, and social sources as complementary signals.
- Do not persist plaintext API keys or tokens in repository files.
- Keep the implementation simple and verifiable with post-change regression checks.

## Implementation Steps

1. Define `models/source_layer.py` with `SourceProvider`, `RefreshCadence`, `FetchStatus`, `SourceSeed`, `RawDocument`, `EvidenceItem`, and `SourceFetchEvent`.
2. Add `storage/source_store.py` with SQLite tables and helpers for seeds, documents, evidence, and fetch events.
3. Add `services/source_connectors.py` with `OfficialJinaConnector`, `NewsApiConnector`, `GitHubRepoConnector`, `RssFeedConnector`, `RedditSearchConnector`, and `DisabledConnector`.
4. Add deterministic evidence extraction in `services/evidence_extractor.py`.
5. Add `services/evidence_service.py` to orchestrate fetch, persist, extract, query, and prompt formatting.
6. Add `services/source_refresh.py` for cadence-based due-source selection.
7. Add `config/source_seeds.py` with default official and news seeds for 钉钉、飞书、企业微信.
8. Add `scripts/index_sources.py` for local seed initialization and indexing.
9. Wire the source layer into `api_app.py` and `services/run_service.py`.
10. Update `tasks/collect_task.py` so Collector prefers Evidence Index but can synthesize sparse source coverage.
11. Document source policies and CLI commands in `docs/PHASE_2_SOURCE_LAYER.md`.
12. Validate with Python unit tests, frontend tests/build, dependency checks, and selected live connector smoke tests.

## Validation Commands

```bash
.venv/bin/python -m unittest discover -s tests
npm test --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m pip check
```

Optional local indexing smoke test:

```bash
.venv/bin/python scripts/index_sources.py --init-defaults --index --provider official --competitor 钉钉 --limit 1
```

GitHub live smoke tests may require `GITHUB_TOKEN` because unauthenticated API calls can hit rate limits quickly.
