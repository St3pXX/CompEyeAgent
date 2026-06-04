"""Tests for services.event_bus — in-memory async event queue."""

import asyncio
import unittest

from services.event_bus import EventBus


class EventBusTest(unittest.TestCase):
    def test_create_returns_queue(self) -> None:
        bus = EventBus()

        async def run():
            q = bus.create("run-1")
            self.assertIsNotNone(q)
            self.assertEqual(bus.get_queue("run-1"), q)

        asyncio.run(run())

    def test_get_queue_returns_none_for_unknown_run(self) -> None:
        bus = EventBus()
        self.assertIsNone(bus.get_queue("nonexistent"))

    def test_publish_and_receive(self) -> None:
        bus = EventBus()

        async def run():
            q = bus.create("run-1")
            bus.publish("run-1", {"type": "agent.started", "message": "hello"})
            event = await asyncio.wait_for(q.get(), timeout=1.0)
            self.assertEqual(event["type"], "agent.started")
            self.assertEqual(event["message"], "hello")

        asyncio.run(run())

    def test_publish_is_noop_when_no_queue(self) -> None:
        bus = EventBus()
        # Should not raise
        bus.publish("nonexistent", {"type": "test"})

    def test_close_sends_sentinel(self) -> None:
        bus = EventBus()

        async def run():
            q = bus.create("run-1")
            bus.close("run-1")
            event = await asyncio.wait_for(q.get(), timeout=1.0)
            self.assertIsNone(event)

        asyncio.run(run())

    def test_close_is_noop_when_no_queue(self) -> None:
        bus = EventBus()
        # Should not raise
        bus.close("nonexistent")

    def test_discard_removes_queue(self) -> None:
        bus = EventBus()

        async def run():
            bus.create("run-1")
            self.assertIsNotNone(bus.get_queue("run-1"))
            bus.discard("run-1")
            self.assertIsNone(bus.get_queue("run-1"))

        asyncio.run(run())

    def test_multiple_events_in_order(self) -> None:
        bus = EventBus()

        async def run():
            q = bus.create("run-1")
            for i in range(5):
                bus.publish("run-1", {"type": "agent.progress", "index": i})
            bus.close("run-1")

            events = []
            while True:
                event = await asyncio.wait_for(q.get(), timeout=1.0)
                if event is None:
                    break
                events.append(event)

            self.assertEqual(len(events), 5)
            self.assertEqual([e["index"] for e in events], [0, 1, 2, 3, 4])

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
