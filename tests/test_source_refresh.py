import unittest
from datetime import UTC, datetime, timedelta

from models.source_layer import FetchStatus, RefreshCadence, SourceFetchEvent, SourceProvider, SourceSeed
from services.source_refresh import due_seeds, is_seed_due


class SourceRefreshTest(unittest.TestCase):
    def test_seed_without_event_is_due(self) -> None:
        seed = SourceSeed(provider=SourceProvider.OFFICIAL, competitor="钉钉", url="https://example.com")

        self.assertTrue(is_seed_due(seed, None))

    def test_daily_seed_is_not_due_before_interval(self) -> None:
        now = datetime(2026, 5, 29, tzinfo=UTC)
        seed = SourceSeed(
            provider=SourceProvider.OFFICIAL,
            competitor="钉钉",
            url="https://example.com",
            cadence=RefreshCadence.DAILY,
        )
        event = SourceFetchEvent(
            seed_id=seed.seed_id,
            provider=seed.provider,
            url=seed.url,
            status=FetchStatus.FETCHED,
            created_at=(now - timedelta(hours=1)).isoformat(),
        )

        self.assertFalse(is_seed_due(seed, event, now=now))

    def test_due_seeds_filters_by_latest_event(self) -> None:
        now = datetime(2026, 5, 29, tzinfo=UTC)
        stale = SourceSeed(provider=SourceProvider.OFFICIAL, competitor="钉钉", url="https://stale.example.com")
        fresh = SourceSeed(provider=SourceProvider.OFFICIAL, competitor="飞书", url="https://fresh.example.com")
        events = {
            fresh.seed_id: SourceFetchEvent(
                seed_id=fresh.seed_id,
                provider=fresh.provider,
                url=fresh.url,
                status=FetchStatus.FETCHED,
                created_at=(now - timedelta(hours=1)).isoformat(),
            )
        }

        self.assertEqual(due_seeds([stale, fresh], events, now=now), [stale])


if __name__ == "__main__":
    unittest.main()
