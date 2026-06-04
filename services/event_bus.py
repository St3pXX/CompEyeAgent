"""In-memory event bus bridging the synchronous coordinator to the async SSE endpoint.

The coordinator runs in a background thread (via FastAPI BackgroundTasks) and
publishes events through :meth:`EventBus.publish`, which uses
``loop.call_soon_threadsafe`` to safely enqueue onto an ``asyncio.Queue``.
The SSE endpoint awaits that queue for push-based delivery with zero polling.

When ``event_bus`` is ``None`` (or a run has no registered queue), callers
fall back to the existing SQLite-polling path — the two modes are fully
compatible.
"""

from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    """Per-run async event queue bridging sync coordinator to async SSE."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Get (and cache) the running event loop. Called lazily from publish()."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_running_loop()
        return self._loop

    def create(self, run_id: str) -> asyncio.Queue[dict[str, Any] | None]:
        """Create a queue for *run_id*. Must be called from an async context."""
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._queues[run_id] = queue
        return queue

    def get_queue(self, run_id: str) -> asyncio.Queue[dict[str, Any] | None] | None:
        """Return the queue for *run_id*, or ``None`` if none exists."""
        return self._queues.get(run_id)

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        """Enqueue *event* for *run_id*. Thread-safe; may be called from a sync thread.

        If no queue exists for *run_id* (e.g. no SSE client connected), the
        call is a no-op — events are still persisted to SQLite by the caller.
        """
        queue = self._queues.get(run_id)
        if queue is None:
            return
        try:
            loop = self._ensure_loop()
            loop.call_soon_threadsafe(queue.put_nowait, event)
        except RuntimeError:
            # Event loop is closed or unavailable — drop silently.
            pass

    def close(self, run_id: str) -> None:
        """Signal end-of-stream by enqueueing ``None`` (the sentinel)."""
        queue = self._queues.get(run_id)
        if queue is None:
            return
        try:
            loop = self._ensure_loop()
            loop.call_soon_threadsafe(queue.put_nowait, None)
        except RuntimeError:
            pass

    def discard(self, run_id: str) -> None:
        """Remove the queue for *run_id* (cleanup after stream closes)."""
        self._queues.pop(run_id, None)
