"""Tests for storage.protocols — verify SQLite implementations satisfy Protocols."""

import tempfile
import unittest
from pathlib import Path

from storage.coordinator_store import SQLiteCoordinatorStore
from storage.protocols import (
    CoordinatorStoreProtocol,
    RunStoreProtocol,
    SourceStoreProtocol,
)
from storage.run_store import SQLiteRunStore
from storage.source_store import SQLiteSourceStore


class ProtocolConformanceTest(unittest.TestCase):
    """Verify that SQLite stores satisfy their Protocol interfaces at runtime."""

    def test_sqlite_run_store_satisfies_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            self.assertIsInstance(store, RunStoreProtocol)

    def test_sqlite_coordinator_store_satisfies_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteCoordinatorStore(Path(tmpdir) / "coordinator.sqlite3")
            self.assertIsInstance(store, CoordinatorStoreProtocol)

    def test_sqlite_source_store_satisfies_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteSourceStore(Path(tmpdir) / "source.sqlite3")
            self.assertIsInstance(store, SourceStoreProtocol)

    def test_arbitrary_class_does_not_satisfy_run_protocol(self) -> None:
        class Fake:
            pass

        self.assertNotIsInstance(Fake(), RunStoreProtocol)


if __name__ == "__main__":
    unittest.main()
