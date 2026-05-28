import tempfile
import unittest
from pathlib import Path

from config.source_seeds import default_source_seeds
from models.source_layer import SourceProvider
from scripts.index_sources import seed_defaults, select_seeds
from storage.source_store import SQLiteSourceStore


class SourceSeedRegistryTest(unittest.TestCase):
    def test_default_source_seeds_cover_initial_competitors_with_sparse_providers(self) -> None:
        seeds = default_source_seeds()
        competitors = {seed.competitor for seed in seeds}
        providers = {seed.provider for seed in seeds}

        self.assertTrue({"钉钉", "飞书", "企业微信"}.issubset(competitors))
        self.assertTrue({SourceProvider.OFFICIAL, SourceProvider.NEWS}.issubset(providers))
        self.assertTrue(all("token" not in str(seed.metadata).lower() for seed in seeds))

    def test_seed_defaults_upserts_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteSourceStore(Path(tmpdir) / "source.sqlite3")

            inserted = seed_defaults(store)
            second_insert = seed_defaults(store)

            self.assertEqual(len(inserted), len(second_insert))
            self.assertEqual(len(store.list_seeds()), len(default_source_seeds()))

    def test_select_seeds_filters_provider_competitor_and_limit(self) -> None:
        seeds = default_source_seeds()

        selected = select_seeds(seeds, provider="official", competitor="钉钉", limit=1)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].provider, SourceProvider.OFFICIAL)
        self.assertEqual(selected[0].competitor, "钉钉")


if __name__ == "__main__":
    unittest.main()
