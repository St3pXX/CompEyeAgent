# Phase 2 Source Layer

Phase 2 adds a source intelligence layer before the CrewAI analysis chain. The goal is to index trusted evidence from official pages, news, technical blogs, GitHub, social media, finance sources, and patent databases before report generation.

Source coverage is intentionally sparse. A competitor or conclusion does not need evidence from every provider category. The source layer should aggregate whatever credible evidence is available, then let the Collector synthesize across official pages, news, blogs, GitHub, social media, finance, and patent sources. Missing coverage from one provider is not a failure; only unsupported conclusions should be marked as gaps.

## First Connectors

The first working connectors are:

- Official source ingestion through Jina Reader. It fetches official product, pricing, and documentation pages, stores raw content in SQLite, and extracts deterministic pricing evidence.
- News API ingestion when `NEWS_API_KEY` is configured. It fetches recent articles as complementary market signals.
- GitHub repository metadata ingestion for public repositories. `GITHUB_TOKEN` is optional for public data but recommended for daily polling because unauthenticated requests can hit rate limits quickly.

## Source Refresh Policy

| Provider | Cadence |
| --- | --- |
| official | daily |
| news | realtime / daily |
| blog | weekly |
| github | daily |
| social | realtime |
| finance | quarterly |
| patent | monthly |

## Local Development

Use `SOURCE_STORE_PATH=data/source_store.sqlite3` for local indexing. API keys for News, GitHub, Crunchbase, and Patent providers are optional in the first milestone.

Initialize the built-in official seeds:

```bash
.venv/bin/python scripts/index_sources.py --init-defaults
```

Index a small slice through Jina Reader:

```bash
.venv/bin/python scripts/index_sources.py --index --provider official --competitor 钉钉 --limit 1
```

Index only sources whose configured cadence is due:

```bash
.venv/bin/python scripts/index_sources.py --index --provider official --due-only
```

## API

- `POST /api/sources/seeds`
- `GET /api/sources/seeds`
- `POST /api/sources/index`
- `GET /api/sources/evidence`
- `GET /api/sources/events`

The first milestone keeps social, finance, and patent connectors behind stable disabled connector boundaries until the required API keys and rate-limit policies are ready.

## Evidence Synthesis Rule

- Prefer high-confidence official, finance, and patent sources when they directly support a claim.
- Use news, blogs, GitHub, Twitter/Reddit, and search results as complementary signals when official sources are incomplete.
- Do not force every dimension to have every source type.
- Mark an item as `待核实` only when no available source can support the claim, not merely because one provider category is missing.
