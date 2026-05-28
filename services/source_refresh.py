"""Refresh cadence helpers for source-layer indexing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from collections.abc import Iterable

from models.source_layer import RefreshCadence, SourceFetchEvent, SourceSeed


CADENCE_INTERVALS = {
    RefreshCadence.REALTIME: timedelta(seconds=0),
    RefreshCadence.DAILY: timedelta(days=1),
    RefreshCadence.WEEKLY: timedelta(weeks=1),
    RefreshCadence.MONTHLY: timedelta(days=30),
    RefreshCadence.QUARTERLY: timedelta(days=90),
}


def due_seeds(
    seeds: Iterable[SourceSeed],
    latest_events: dict[str, SourceFetchEvent | None],
    *,
    now: datetime | None = None,
) -> list[SourceSeed]:
    current_time = now or datetime.now(UTC)
    return [seed for seed in seeds if is_seed_due(seed, latest_events.get(seed.seed_id), now=current_time)]


def is_seed_due(seed: SourceSeed, latest_event: SourceFetchEvent | None, *, now: datetime | None = None) -> bool:
    if not seed.enabled:
        return False
    if seed.cadence == RefreshCadence.MANUAL:
        return latest_event is None
    if latest_event is None:
        return True

    interval = CADENCE_INTERVALS.get(seed.cadence)
    if interval is None:
        return True
    return _parse_time(latest_event.created_at) + interval <= (now or datetime.now(UTC))


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
