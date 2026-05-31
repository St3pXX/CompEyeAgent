#!/usr/bin/env python3
"""FastAPI entrypoint for the Phase 1.5 online product demo."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import config.settings
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from models.coordinator import ScratchpadWriteRequest
from models.schema import CreateRunRequest, CreateRunResponse, RunDetailResponse
from models.source_layer import SourceSeed
from services.coordinator_foundation import CoordinatorFoundationService
from services.evidence_service import EvidenceService
from services.run_service import RunService
from storage.coordinator_store import SQLiteCoordinatorStore
from storage.run_store import SQLiteRunStore, TERMINAL_STATUSES
from storage.source_store import SQLiteSourceStore


store = SQLiteRunStore()
coordinator_store = SQLiteCoordinatorStore()
coordinator_service = CoordinatorFoundationService(coordinator_store)
source_store = SQLiteSourceStore()
evidence_service = EvidenceService(source_store)
run_service = RunService(store, evidence_service=evidence_service, coordinator_service=coordinator_service)
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

app = FastAPI(
    title="CompEye Agent API",
    description="Phase 1.5 API for online competitor analysis runs, events, artifacts, and future DAG views.",
    version="1.5.0",
)

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
    return {"status": "ok"}


@app.post("/api/runs", response_model=CreateRunResponse, status_code=202)
def create_run(request: CreateRunRequest, background_tasks: BackgroundTasks) -> CreateRunResponse:
    run = run_service.create_run(request.input, allow_retry=request.allow_retry)
    background_tasks.add_task(run_service.execute_run, run.run_id, allow_retry=request.allow_retry)
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
        background_tasks.add_task(run_service.execute_run, retry.run_id, allow_retry=True)
        return CreateRunResponse(run=retry)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


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
    while True:
        for event in store.list_events(run_id, after_event_id=last_event_id):
            last_event_id = event.event_id
            yield _sse(event.type, event.model_dump(), event_id=event.event_id)

        run = store.get_run(run_id)
        if run.status in TERMINAL_STATUSES:
            yield _sse("stream.closed", {"run_id": run_id, "status": run.status})
            break

        yield ": heartbeat\n\n"
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
