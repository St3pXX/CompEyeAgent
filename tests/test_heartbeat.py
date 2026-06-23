"""Tests for the node heartbeat — low-emphasis "still generating…" events.

The heartbeat runs on a daemon thread while a node's LLM call is in flight.
These tests verify it emits periodically and stops cleanly on exit (including
on exception), without requiring a real LLM call.
"""

import time
import unittest
from unittest.mock import MagicMock

import services.coordinator_loop as cl_module
from services.coordinator_loop import CoordinatorLoopService


def _make_service() -> CoordinatorLoopService:
    """Construct a CoordinatorLoopService with mocked dependencies."""
    run_store = MagicMock()
    foundation = MagicMock()
    return CoordinatorLoopService(run_store, foundation)


class HeartbeatDuringNodeTest(unittest.TestCase):
    def test_emits_heartbeat_while_block_runs(self) -> None:
        service = _make_service()
        emit = MagicMock()
        service._emit = emit  # type: ignore[method-assign]

        original_interval = cl_module.HEARTBEAT_INTERVAL_SECONDS
        cl_module.HEARTBEAT_INTERVAL_SECONDS = 0.05
        try:
            with service._heartbeat_during_node("run-1", "collect"):
                time.sleep(0.2)  # ~4 heartbeat intervals
        finally:
            cl_module.HEARTBEAT_INTERVAL_SECONDS = original_interval

        # Should have emitted at least 2 heartbeat events during 0.2s.
        self.assertGreaterEqual(emit.call_count, 2)
        # Every call carries the stage and heartbeat payload marker.
        for call in emit.call_args_list:
            args, kwargs = call
            self.assertEqual(args[0], "run-1")
            self.assertEqual(args[1], "agent.progress")
            self.assertEqual(kwargs.get("stage"), "collect")
            self.assertEqual(kwargs.get("payload", {}).get("kind"), cl_module.HEARTBEAT_KIND)

    def test_stops_emitting_after_block_exits(self) -> None:
        service = _make_service()
        emit = MagicMock()
        service._emit = emit  # type: ignore[method-assign]

        original_interval = cl_module.HEARTBEAT_INTERVAL_SECONDS
        cl_module.HEARTBEAT_INTERVAL_SECONDS = 0.05
        try:
            with service._heartbeat_during_node("run-1", "write"):
                time.sleep(0.15)
            count_after_exit = emit.call_count
            # Wait well beyond the interval after exit.
            time.sleep(0.2)
        finally:
            cl_module.HEARTBEAT_INTERVAL_SECONDS = original_interval

        # No new heartbeats should have been emitted after the block exited.
        self.assertEqual(emit.call_count, count_after_exit)

    def test_stops_cleanly_on_exception(self) -> None:
        service = _make_service()
        emit = MagicMock()
        service._emit = emit  # type: ignore[method-assign]

        original_interval = cl_module.HEARTBEAT_INTERVAL_SECONDS
        cl_module.HEARTBEAT_INTERVAL_SECONDS = 0.05
        try:
            with self.assertRaises(RuntimeError):
                with service._heartbeat_during_node("run-1", "verify"):
                    time.sleep(0.12)
                    raise RuntimeError("node failed")
            count_after_exit = emit.call_count
            time.sleep(0.15)
        finally:
            cl_module.HEARTBEAT_INTERVAL_SECONDS = original_interval

        # Heartbeat must not keep firing after the exception propagated.
        self.assertEqual(emit.call_count, count_after_exit)


if __name__ == "__main__":
    unittest.main()
