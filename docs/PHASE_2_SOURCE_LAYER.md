# Phase 2 Source Layer

This document covers the completed Source Layer sub-milestone within Phase 2, not the whole Phase 2 roadmap. The goal is to index trusted evidence from official pages, news, technical blogs, GitHub, social media, finance sources, and patent databases before report generation.

Source coverage is intentionally sparse. A competitor or conclusion does not need evidence from every provider category. The source layer should aggregate whatever credible evidence is available, then let the Collector synthesize across official pages, news, blogs, GitHub, social media, finance, and patent sources. Missing coverage from one provider is not a failure; only unsupported conclusions should be marked as gaps.

## Completed Connectors

The Phase 2 working connectors are:

- Official source ingestion through Jina Reader. It fetches official product, pricing, and documentation pages, stores raw content in SQLite, and extracts deterministic pricing evidence.
- News API ingestion when `NEWS_API_KEY` is configured. It fetches recent articles as complementary market signals.
- GitHub repository metadata ingestion for public repositories. `GITHUB_TOKEN` is optional for public data but recommended for daily polling because unauthenticated requests can hit rate limits quickly.
- Blog/RSS ingestion for technical blogs, product update feeds, and media RSS/Atom feeds. It uses standard RSS/Atom parsing and does not require an API key.
- Reddit search ingestion for lightweight social/user-feedback signals. It does not require an API key but should use a descriptive `REDDIT_USER_AGENT`; some environments may still receive Reddit 403 responses, so production use should add a formal API or proxy policy.

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

Add a custom RSS/Atom seed through the API, then index it:

```bash
curl -X POST http://127.0.0.1:8000/api/sources/seeds \
  -H 'Content-Type: application/json' \
  -d '{"provider":"blog","competitor":"示例产品","url":"https://example.com/feed.xml","label":"示例产品博客","cadence":"weekly","metadata":{"dimension":"技术动态","indicators":["发布","架构"]}}'

.venv/bin/python scripts/index_sources.py --index --provider blog --competitor 示例产品
```

Add a Reddit social search seed:

```bash
curl -X POST http://127.0.0.1:8000/api/sources/seeds \
  -H 'Content-Type: application/json' \
  -d '{"provider":"social","competitor":"示例产品","url":"reddit://search?query=示例产品","label":"示例产品 Reddit 搜索","cadence":"realtime","metadata":{"query":"示例产品","dimension":"用户反馈","indicators":["score","comments"],"limit":5}}'

.venv/bin/python scripts/index_sources.py --index --provider social --competitor 示例产品
```

## API

- `POST /api/sources/seeds`
- `GET /api/sources/seeds`
- `POST /api/sources/index`
- `GET /api/sources/evidence`
- `GET /api/sources/events`

Phase 2 keeps finance and patent connectors behind stable disabled connector boundaries until the required API keys and rate-limit policies are ready. Twitter remains out of scope until an API bearer-token policy is added.

## Evidence Synthesis Rule

- Prefer high-confidence official, finance, and patent sources when they directly support a claim.
- Use news, blogs, GitHub, Twitter/Reddit, and search results as complementary signals when official sources are incomplete.
- Do not force every dimension to have every source type.
- Mark an item as `待核实` only when no available source can support the claim, not merely because one provider category is missing.
