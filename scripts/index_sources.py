"""Initialize and index Phase 2 source-layer seeds."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.source_seeds import default_source_seeds
from models.source_layer import SourceProvider, SourceSeed
from services.evidence_service import EvidenceService
from services.source_refresh import due_seeds
from storage.source_store import SQLiteSourceStore


def seed_defaults(store: SQLiteSourceStore) -> list[SourceSeed]:
    seeds: list[SourceSeed] = []
    for seed in default_source_seeds():
        seeds.append(store.upsert_seed(seed))
    return seeds


def select_seeds(
    seeds: Iterable[SourceSeed],
    *,
    provider: str | None = None,
    competitor: str | None = None,
    limit: int | None = None,
) -> list[SourceSeed]:
    selected: list[SourceSeed] = []
    for seed in seeds:
        if provider and seed.provider.value != provider:
            continue
        if competitor and seed.competitor != competitor:
            continue
        selected.append(seed)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def index_seeds(service: EvidenceService, seeds: Iterable[SourceSeed]) -> int:
    total_evidence = 0
    for seed in seeds:
        evidence_items = service.index_seed(seed)
        total_evidence += len(evidence_items)
        print(
            f"indexed provider={seed.provider.value} competitor={seed.competitor} "
            f"url={seed.url} evidence={len(evidence_items)}"
        )
    return total_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and index Phase 2 source-layer seeds.")
    parser.add_argument("--init-defaults", action="store_true", help="Upsert the built-in official source seeds.")
    parser.add_argument("--index", action="store_true", help="Fetch selected seeds and extract evidence.")
    parser.add_argument("--provider", choices=[provider.value for provider in SourceProvider], help="Provider filter.")
    parser.add_argument("--competitor", help="Competitor filter, for example 钉钉.")
    parser.add_argument("--limit", type=int, help="Maximum number of selected seeds to index.")
    parser.add_argument("--due-only", action="store_true", help="Only index seeds whose refresh cadence is due.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.init_defaults and not args.index:
        parser.error("choose at least one action: --init-defaults or --index")

    store = SQLiteSourceStore()
    if args.init_defaults:
        seeds = seed_defaults(store)
        print(f"initialized default source seeds: {len(seeds)}")

    if args.index:
        service = EvidenceService(store)
        seeds = select_seeds(
            store.list_seeds(enabled_only=True),
            provider=args.provider,
            competitor=args.competitor,
            limit=args.limit,
        )
        if args.due_only:
            latest_events = {seed.seed_id: store.latest_fetch_event(seed.seed_id) for seed in seeds}
            seeds = due_seeds(seeds, latest_events)
        print(f"selected source seeds: {len(seeds)}")
        total_evidence = index_seeds(service, seeds)
        print(f"total evidence extracted: {total_evidence}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
