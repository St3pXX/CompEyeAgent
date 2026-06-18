#!/usr/bin/env python3
"""FastAPI entrypoint for the Phase 1.5 online product demo."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import config.settings
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from models.coordinator import ScratchpadWriteRequest
from models.schema import CreateRunRequest, CreateRunResponse, RunDetailResponse
from models.source_layer import SourceSeed
from services.coordinator_foundation import CoordinatorFoundationService
from services.evidence_service import EvidenceService
from services.event_bus import EventBus
from services.run_service import RunService
import services.verification
from services.telemetry import get_prometheus_content_type, get_prometheus_metrics, init_telemetry, record_run_created
import services.llm_telemetry
from storage.coordinator_store import SQLiteCoordinatorStore
from storage.run_store import SQLiteRunStore, TERMINAL_STATUSES
from storage.source_store import SQLiteSourceStore


_backfill_done = False


def _backfill_missing_reviews() -> None:
    global _backfill_done
    if _backfill_done:
        return
    _backfill_done = True
    try:
        runs = store.list_runs(limit=500)
        for run in runs:
            if run.status != "needs_review":
                continue
            existing = store.get_review_by_run(run.run_id)
            if existing is not None:
                continue
            events = store.list_events(run.run_id)
            issues = _extract_issues_from_events(events) or _extract_issues_from_artifacts(run.run_id)
            if issues:
                store.create_review(run.run_id, issues)
            else:
                store.create_review(run.run_id, ["质检未通过，详见 Dashboard 页面"])
    except Exception:
        pass


def _extract_issues_from_events(events) -> list[str] | None:
    for event in events:
        payload = getattr(event, "payload", None)
        if isinstance(payload, dict) and payload.get("passed") is False:
            return None
        if isinstance(payload, dict) and "issues" in payload:
            return payload["issues"]
    return None


def _extract_issues_from_artifacts(run_id: str) -> list[str] | None:
    try:
        artifacts = store.list_artifacts(run_id)
        for artifact in artifacts:
            if artifact.kind == "verifier_json":
                parsed = services.verification.parse_verifier_result(artifact.content)
                if parsed:
                    return parsed.get("issues", [])
    except Exception:
        pass
    return None


store = SQLiteRunStore()
coordinator_store = SQLiteCoordinatorStore()
coordinator_service = CoordinatorFoundationService(coordinator_store)
source_store = SQLiteSourceStore()
evidence_service = EvidenceService(source_store)

# Long-term memory (optional — gracefully disabled if ChromaDB unavailable)
memory_service = None
try:
    from services.memory_service import MemoryService
    from storage.vector_store import VectorStore
    memory_service = MemoryService(VectorStore(), store)
except Exception:
    pass

run_service = RunService(
    store,
    evidence_service=evidence_service,
    coordinator_service=coordinator_service,
    memory_service=memory_service,
)
event_bus = EventBus()
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

app = FastAPI(
    title="CompEye Agent API",
    description="Phase 1.5 API for online competitor analysis runs, events, artifacts, and future DAG views.",
    version="1.5.0",
)

# Initialize OpenTelemetry (no-op if COMPETEYE_OTEL_ENABLED != "true")
if init_telemetry():
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass

# Register LLM token tracking callback
services.llm_telemetry.register_litellm_callback()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


@app.get("/health")
def health() -> dict[str, str]:
    _backfill_missing_reviews()
    return {"status": "ok"}


@app.get("/metrics")
def metrics_endpoint() -> StreamingResponse:
    """Prometheus-compatible metrics endpoint."""
    return StreamingResponse(
        iter([get_prometheus_metrics()]),
        media_type=get_prometheus_content_type(),
    )


@app.post("/api/runs", response_model=CreateRunResponse, status_code=202)
def create_run(request: CreateRunRequest, background_tasks: BackgroundTasks) -> CreateRunResponse:
    run = run_service.create_run(request.input, allow_retry=request.allow_retry)
    record_run_created()
    event_bus.create(run.run_id)
    background_tasks.add_task(run_service.execute_run, run.run_id, allow_retry=request.allow_retry, event_bus=event_bus)
    return CreateRunResponse(run=run)


@app.get("/api/runs")
def list_runs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    return {"runs": store.list_runs(limit=limit)}


@app.get("/api/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str) -> RunDetailResponse:
    try:
        return RunDetailResponse(
            run=store.get_run(run_id),
            events=store.list_events(run_id),
            artifacts=store.list_artifacts(run_id),
            sources=store.list_sources(run_id),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/api/runs/{run_id}/events")
def list_events(run_id: str, after_event_id: int = Query(default=0, ge=0)) -> dict[str, object]:
    try:
        store.get_run(run_id)
        return {"events": store.list_events(run_id, after_event_id=after_event_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/sse/runs/{run_id}")
async def stream_run_events(run_id: str, after_event_id: int = Query(default=0, ge=0)) -> StreamingResponse:
    try:
        store.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None

    return StreamingResponse(
        _event_stream(run_id, after_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{run_id}/artifacts")
def list_artifacts(run_id: str) -> dict[str, object]:
    try:
        store.get_run(run_id)
        return {"artifacts": store.list_artifacts(run_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/api/artifacts/{artifact_id}")
def get_artifact(artifact_id: str) -> dict[str, object]:
    try:
        return {"artifact": store.get_artifact(artifact_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Artifact not found") from None


@app.get("/api/runs/{run_id}/sources")
def list_sources(run_id: str) -> dict[str, object]:
    try:
        store.get_run(run_id)
        return {"sources": store.list_sources(run_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, object]:
    try:
        return {"run": run_service.cancel_run(run_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/api/runs/{run_id}/retry", response_model=CreateRunResponse, status_code=202)
def retry_run(run_id: str, background_tasks: BackgroundTasks) -> CreateRunResponse:
    try:
        retry = run_service.retry_run(run_id)
        event_bus.create(retry.run_id)
        background_tasks.add_task(run_service.execute_run, retry.run_id, allow_retry=True, event_bus=event_bus)
        return CreateRunResponse(run=retry)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/api/runs/{run_id}/dag/{node_key}/retry", status_code=202)
def retry_run_node(run_id: str, node_key: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    try:
        run = store.get_run(run_id)
        coordinator_store.get_node(run_id, node_key)
        event_bus.create(run_id)
        background_tasks.add_task(run_service.retry_node, run_id, node_key, allow_retry=True, event_bus=event_bus)
        return {"run": run, "node_key": node_key}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run or DAG node not found") from None


@app.get("/api/runs/{run_id}/dag")
def get_run_dag(run_id: str) -> dict[str, object]:
    try:
        run = store.get_run(run_id)
        return {"dag": coordinator_service.ensure_default_dag(run_id, run.input.model_dump())}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/api/runs/{run_id}/scratchpad")
def get_run_scratchpad(run_id: str) -> dict[str, object]:
    try:
        store.get_run(run_id)
        return {"items": coordinator_service.list_scratchpad(run_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/api/runs/{run_id}/scratchpad", status_code=201)
def write_run_scratchpad(run_id: str, request: ScratchpadWriteRequest) -> dict[str, object]:
    try:
        store.get_run(run_id)
        return {"item": coordinator_service.write_scratchpad(run_id, request)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/api/runs/{run_id}/inspector")
def get_run_inspector(run_id: str) -> dict[str, object]:
    try:
        store.get_run(run_id)
        return {"inspector": coordinator_service.inspector_summary(run_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/api/runs/{run_id}/trace")
def get_run_trace(run_id: str) -> dict[str, object]:
    return run_service.empty_extension_payload(run_id, "trace")


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

@app.get("/api/reviews")
def list_reviews(
    status: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    from models.schema import ReviewStatus
    review_status: ReviewStatus | None = status if status in ("pending", "in_review", "approved", "rejected") else None
    return {"reviews": store.list_reviews(status=review_status, run_id=run_id, limit=limit)}


@app.get("/api/reviews/{review_id}")
def get_review(review_id: str) -> dict[str, object]:
    try:
        return {"review": store.get_review(review_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found") from None


@app.get("/api/runs/{run_id}/review")
def get_run_review(run_id: str) -> dict[str, object]:
    review = store.get_review_by_run(run_id)
    if review is None:
        raise HTTPException(status_code=404, detail="No review found for this run")
    return {"review": review}


class ReviewActionRequest(BaseModel):
    notes: str | None = None
    assignee: str | None = None


@app.post("/api/reviews/{review_id}/approve")
def approve_review(review_id: str, request: ReviewActionRequest | None = None) -> dict[str, object]:
    notes = request.notes if request else None
    try:
        return {"review": store.update_review(review_id, status="approved", review_notes=notes)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found") from None


@app.post("/api/reviews/{review_id}/reject")
def reject_review(review_id: str, request: ReviewActionRequest | None = None) -> dict[str, object]:
    notes = request.notes if request else None
    try:
        return {"review": store.update_review(review_id, status="rejected", review_notes=notes)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found") from None


@app.post("/api/reviews/{review_id}/assign")
def assign_review(review_id: str, request: ReviewActionRequest) -> dict[str, object]:
    if not request.assignee:
        raise HTTPException(status_code=400, detail="assignee is required")
    try:
        return {"review": store.update_review(review_id, status="in_review", assigned_to=request.assignee)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found") from None


# ---------------------------------------------------------------------------
# Aggregate stats & cost tracking
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats() -> dict[str, object]:
    """Aggregate statistics across all runs."""
    runs = store.list_runs(limit=1000)
    by_status: dict[str, int] = {}
    for r in runs:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    reviews = store.list_reviews(limit=1000)
    pending_reviews = sum(1 for r in reviews if r.status == "pending")
    return {
        "total_runs": len(runs),
        "by_status": by_status,
        "pending_reviews": pending_reviews,
        "total_reviews": len(reviews),
    }


@app.get("/api/costs")
def get_costs() -> dict[str, object]:
    """Token cost tracking — aggregates LLM token usage from events."""
    runs = store.list_runs(limit=100)
    cost_data: list[dict[str, object]] = []
    for run in runs:
        events = store.list_events(run.run_id)
        total_input = 0
        total_output = 0
        for event in events:
            tokens = event.payload.get("tokens", {})
            if isinstance(tokens, dict):
                total_input += tokens.get("input", 0)
                total_output += tokens.get("output", 0)
        cost_data.append({
            "run_id": run.run_id,
            "status": run.status,
            "created_at": run.created_at,
            "input_tokens": total_input,
            "output_tokens": total_output,
        })
    return {"costs": cost_data}


@app.post("/api/sources/seeds", status_code=201)
def create_source_seed(seed: SourceSeed) -> dict[str, object]:
    return {"seed": source_store.upsert_seed(seed)}


@app.get("/api/sources/seeds")
def list_source_seeds(enabled_only: bool = False) -> dict[str, object]:
    return {"seeds": source_store.list_seeds(enabled_only=enabled_only)}


@app.post("/api/sources/index")
def index_source_seed(seed: SourceSeed) -> dict[str, object]:
    return {"evidence": evidence_service.index_seed(seed)}


@app.get("/api/sources/evidence")
def query_source_evidence(competitor: str, dimension: list[str] = Query(default=[])) -> dict[str, object]:
    return {"evidence": evidence_service.query_evidence(competitor, dimension)}


@app.get("/api/sources/events")
def list_source_fetch_events(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, object]:
    return {"events": source_store.list_fetch_events(limit=limit)}


@app.get("/")
def serve_frontend_root() -> FileResponse:
    return _frontend_index()


@app.get("/{path:path}")
def serve_frontend_route(path: str) -> FileResponse:
    if path.startswith(("api/", "sse/")):
        raise HTTPException(status_code=404, detail="Not found")
    return _frontend_index()


async def _event_stream(run_id: str, after_event_id: int) -> AsyncIterator[str]:
    last_event_id = after_event_id

    # Phase 1: drain any events already persisted to SQLite.
    for event in store.list_events(run_id, after_event_id=last_event_id):
        last_event_id = event.event_id
        yield _sse(event.type, event.model_dump(), event_id=event.event_id)

    # Check if the run already finished before we started streaming.
    run = store.get_run(run_id)
    if run.status in TERMINAL_STATUSES:
        yield _sse("stream.closed", {"run_id": run_id, "status": run.status})
        return

    # Phase 2: prefer in-memory event queue (push-based, zero polling).
    queue = event_bus.get_queue(run_id)
    if queue is not None:
        async for event_dict in _queue_stream(run_id, queue):
            if event_dict is None:
                run = store.get_run(run_id)
                yield _sse("stream.closed", {"run_id": run_id, "status": run.status})
                return
            eid = event_dict.get("event_id")
            yield _sse(event_dict["type"], event_dict, event_id=eid)
    else:
        # Fallback: legacy SQLite polling (for runs started before this server).
        async for event_dict in _polling_stream(run_id, last_event_id):
            if event_dict is None:
                run = store.get_run(run_id)
                yield _sse("stream.closed", {"run_id": run_id, "status": run.status})
                return
            if event_dict.get("_heartbeat"):
                yield ": heartbeat\n\n"
            else:
                eid = event_dict.get("event_id")
                yield _sse(event_dict["type"], event_dict, event_id=eid)


async def _queue_stream(
    run_id: str, queue: asyncio.Queue[dict[str, object] | None],
) -> AsyncIterator[dict[str, object] | None]:
    """Push-based stream: await the in-memory queue."""
    try:
        while True:
            event_dict = await queue.get()
            yield event_dict
            if event_dict is None:
                return
    finally:
        event_bus.discard(run_id)


async def _polling_stream(run_id: str, after_event_id: int) -> AsyncIterator[dict[str, object] | None]:
    """Fallback polling stream for runs without an in-memory queue."""
    last_event_id = after_event_id
    while True:
        for event in store.list_events(run_id, after_event_id=last_event_id):
            last_event_id = event.event_id
            yield event.model_dump()

        run = store.get_run(run_id)
        if run.status in TERMINAL_STATUSES:
            yield None
            return

        yield {"_heartbeat": True}
        await asyncio.sleep(1)


def _sse(event_type: str, data: dict[str, object], *, event_id: int | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False, default=str)}")
    return "\n".join(lines) + "\n\n"


def _frontend_index() -> FileResponse:
    if not FRONTEND_INDEX.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found. Run `npm run build` in frontend/.")
    return FileResponse(FRONTEND_INDEX)
