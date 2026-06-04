# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CompEyeAgent is a multi-agent competitive analysis system (Python 3.11+). Four specialized CrewAI agents run in a sequential pipeline — Collector, Analyzer, Writer, Verifier — to automate competitive research with provenance-tracked outputs. The UI and documentation are primarily in Chinese; the domain is Chinese SaaS/product competitive analysis.

## Commands

### Backend

```bash
python3 -m pip install -r requirements.txt    # install dependencies
python3 -m pytest                              # run all backend tests
python3 -m pytest tests/test_run_service.py    # run a single test file
uvicorn api_app:app --host 0.0.0.0 --port 8000 # start FastAPI (production entry point)
streamlit run app.py                            # start Streamlit UI (Phase 1 legacy)
python main.py '<json>'                         # CLI single-run analysis
python test_api.py                              # test MiMo API connectivity (standalone)
```

### Frontend (React 19 + TypeScript + Vite)

```bash
cd frontend
npm install          # install deps
npm run dev          # dev server on :5173, proxies /api and /sse to FastAPI :8000
npm run build        # typecheck + production build → dist/
npm test             # vitest unit tests
```

### Source Indexing CLI

```bash
python scripts/index_sources.py --init-defaults                        # seed default sources
python scripts/index_sources.py --index --provider official --competitor 钉钉 --limit 1
python scripts/index_sources.py --index --provider official --due-only
```

## Architecture

### Execution Flow

```
User Input → CompetitorInput (Pydantic) → RunService.create_run()
  → CoordinatorLoopService.execute() [DAG state machine]
    → run_analysis() [CrewAI sequential chain]
      → Collector → Analyzer → Writer → Verifier
  → progress_callback → agent_events → SSE stream → Frontend
```

### Three Entry Points

- **`main.py`** — CLI. Calls `runner.run_analysis()` directly.
- **`app.py`** — Streamlit UI (Phase 1 legacy). Also calls `runner.run_analysis()` directly.
- **`api_app.py`** — FastAPI (primary production entry). Wraps `run_analysis()` via `RunService` with background execution, event logging, artifact persistence, and DAG state. Serves the React frontend from `frontend/dist/` for non-API routes.

### Core Pipeline (CrewAI Sequential Chain)

Defined in `crew/crew.py`. Four agents chained with `context=[previous_task]`:
1. **Collector** (`crew/agents/collector.py`) — MiMo-V2.5 + WebSearchTool. Fetches public info. Receives pre-indexed evidence via `evidenceIndex` prompt variable.
2. **Analyzer** (`crew/agents/analyzer.py`) — MiMo-V2.5. SWOT/comparison structured analysis.
3. **Writer** (`crew/agents/writer.py`) — MiMo-V2.5. Generates Markdown report with `[来源: URL]` annotations.
4. **Verifier** (`crew/agents/verifier.py`) — MiMo-V2.5-Pro (1M context, deep reasoning). Independent quality check — does NOT inherit Writer's history.

### Provenance Guard (`runner.py`)

After the CrewAI chain completes, `runner.py` applies multi-layer checks:
- Regex-based: report must contain provenance/source index block, at least one URL, matching source tag counts.
- Verifier JSON parse: checks `passed`, `confidence < 60`, individual issues.
- On failure with `allow_retry=True`: re-runs Writer + Verifier once with issues injected. Second failure returns issues (not zero-exit).

### DAG-Based Coordinator (Phase 2)

`services/coordinator_foundation.py` defines a 4-node linear DAG (`collect → analyze → write → verify`). `services/coordinator_loop.py` is the DAG scheduler — finds ready nodes, executes them, supports node-level retry, marks descendants as skipped on failure. Currently wraps the entire CrewAI chain in the `collect` node; per-node executors are a future target.

### Three SQLite Databases

Each store uses `threading.RLock` and auto-creates tables on init:
- **Run Store** (`storage/run_store.py`) — `analysis_runs`, `agent_events`, `artifacts`, `source_references`. Path: `data/run_store.sqlite3`.
- **Coordinator Store** (`storage/coordinator_store.py`) — `dag_nodes`, `scratchpad_items`. Path: `data/coordinator_store.sqlite3`.
- **Source Store** (`storage/source_store.py`) — `source_seeds`, `raw_documents`, `evidence_items`, `source_fetch_events`. Path: `data/source_store.sqlite3`.

### Source Intelligence Layer (Phase 2)

Five connector implementations in `services/source_connectors.py` follow a common protocol: `OfficialJinaConnector`, `NewsApiConnector`, `GitHubRepoConnector`, `RssFeedConnector`, `RedditSearchConnector`. Evidence is extracted deterministically (keyword-based, not LLM) in `services/evidence_extractor.py`, then injected into the Collector prompt via `services/evidence_service.py`.

### Frontend (React)

Three pages in `frontend/src/pages/`:
- **DemoPage** (`/demo`) — Conversational task creation, submits to `POST /api/runs`.
- **DashboardPage** (`/dashboard/:runId`) — Real-time SSE-driven execution tracking with agent stage cards and DAG inspector.
- **ReportPage** (`/reports/:runId`) — Report detail with Markdown rendering, source cards, and download actions.

API client: `frontend/src/api/client.ts`. Type definitions mirror Pydantic models in `frontend/src/api/types.ts`. All CSS is hand-written in `frontend/src/styles.css` (no framework).

### Models

- `models/schema.py` — Core domain: `CompetitorInput`, `RunRecord`, `AgentEvent`, `ArtifactRecord`, `ReportArtifact`, `VerificationIssue`, `RunStatus`, `EventType`, API request/response contracts.
- `models/coordinator.py` — `DAGNode`, `DAGEdge`, `DAGView`, `ScratchpadItem`.
- `models/source_layer.py` — `SourceSeed`, `RawDocument`, `EvidenceItem`, `SourceFetchEvent`, enums.
- `models/provenance.py` — `SourceRef`, `Provenance`.

## Configuration

- Copy `.env.example` to `.env`. Required: `MIMO_BASE_URL`, `MIMO_API_KEY`.
- `config/settings.py` is the central config module — on import it strips proxy env vars, loads `.env`, exports model constants, and provides `create_llm(model_name)` factory.
- Per-agent model overrides: `COLLECTOR_MODEL`, `ANALYZER_MODEL`, `WRITER_MODEL`, `VERIFIER_MODEL`.
- LLM defaults: `temperature=0.7`, `top_p=0.95`, `max_completion_tokens=2048`, thinking disabled.

## Development Conventions (from AGENTS.md)

- Read related modules and tests before modifying; preserve existing naming and structure.
- Prefer small, focused changes; avoid introducing large abstractions for single-point needs.
- When touching agent logic, task chains, provenance, run store, or SSE events, consider end-to-end behavior.
- Use existing Pydantic schemas in `models/` for structured objects (reports, evidence, claims).
- Never commit secrets, API keys, SSH keys, database files, logs, build artifacts, or `frontend/dist/`.
- `.env` is local-only; configuration examples go in `.env.example`.
- Do not use `git add -A` unless explicitly asked; do not revert user changes or touch unrelated uncommitted files.
- Check existing `.gitignore` before adding new ignore rules.

## Verification

- For Python changes: run relevant pytest; run full `python3 -m pytest` when impact is unclear.
- For frontend changes: at minimum run `cd frontend && npm run build`; check key pages in browser for layout/interaction changes.
- For API/SSE/run store changes: verify the local backend-to-frontend proxy chain end-to-end.
- If verification is blocked by missing deps, keys, or external services, state what was not verified and why.
