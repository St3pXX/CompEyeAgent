import tempfile
import sys
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from models.schema import CompetitorInput
from services.run_service import RunService
from storage.run_store import SQLiteRunStore


class RunServiceTest(unittest.TestCase):
    def test_execute_run_skips_cancelled_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "runs.sqlite3")
            service = RunService(store)
            run = service.create_run(
                CompetitorInput(
                    productName="目标产品",
                    competitors=["竞品A"],
                    dimensions=[],
                )
            )
            service.cancel_run(run.run_id)
            run_analysis = Mock()
            fake_runner = SimpleNamespace(run_analysis=run_analysis)

            with patch.dict(sys.modules, {"runner": fake_runner}):
                service.execute_run(run.run_id)

            run_analysis.assert_not_called()
            self.assertEqual(store.get_run(run.run_id).status, "cancelled")


if __name__ == "__main__":
    unittest.main()
