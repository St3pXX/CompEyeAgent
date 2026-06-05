"""Tests for services.resilience — circuit breaker, timeouts."""

import time
import unittest

from services.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    get_circuit_breaker,
    run_with_timeout,
)


class CircuitBreakerTest(unittest.TestCase):
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_seconds=1.0)
        self.assertEqual(cb.state, "closed")

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_seconds=10.0)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, "open")

    def test_rejects_when_open(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_seconds=10.0)
        cb.record_failure()
        cb.record_failure()
        with self.assertRaises(CircuitOpenError):
            cb.check()

    def test_transitions_to_half_open_after_cooldown(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=0.1)
        cb.record_failure()
        self.assertEqual(cb.state, "open")
        time.sleep(0.15)
        self.assertEqual(cb.state, "half_open")

    def test_closes_on_success_in_half_open(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.record_success()
        self.assertEqual(cb.state, "closed")

    def test_reopens_on_failure_in_half_open(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=0.1)
        cb.record_failure()
        time.sleep(0.15)
        self.assertEqual(cb.state, "half_open")
        cb.record_failure()
        self.assertEqual(cb.state, "open")

    def test_call_records_success(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_seconds=10.0)
        result = cb.call(lambda: 42)
        self.assertEqual(result, 42)
        self.assertEqual(cb.state, "closed")

    def test_call_records_failure(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_seconds=10.0)

        def failing():
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            cb.call(failing)
        with self.assertRaises(ValueError):
            cb.call(failing)
        self.assertEqual(cb.state, "open")

    def test_reset_closes_breaker(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=100.0)
        cb.record_failure()
        self.assertEqual(cb.state, "open")
        cb.reset()
        self.assertEqual(cb.state, "closed")


class CircuitBreakerRegistryTest(unittest.TestCase):
    def test_returns_same_instance_for_same_provider(self) -> None:
        a = get_circuit_breaker("provider-x", failure_threshold=3, cooldown_seconds=10.0)
        b = get_circuit_breaker("provider-x")
        self.assertIs(a, b)

    def test_different_instances_for_different_providers(self) -> None:
        a = get_circuit_breaker("provider-a", failure_threshold=3, cooldown_seconds=10.0)
        b = get_circuit_breaker("provider-b", failure_threshold=3, cooldown_seconds=10.0)
        self.assertIsNot(a, b)


class RunWithTimeoutTest(unittest.TestCase):
    def test_runs_without_timeout(self) -> None:
        result = run_with_timeout(lambda: 42)
        self.assertEqual(result, 42)

    def test_runs_within_timeout(self) -> None:
        result = run_with_timeout(lambda: 42, timeout_seconds=5.0)
        self.assertEqual(result, 42)

    def test_raises_on_timeout(self) -> None:
        def slow():
            time.sleep(2.0)
            return 42

        with self.assertRaises(TimeoutError):
            run_with_timeout(slow, timeout_seconds=0.2)

    def test_passes_args_and_kwargs(self) -> None:
        def add(a, b, c=0):
            return a + b + c

        result = run_with_timeout(add, 1, 2, c=3, timeout_seconds=5.0)
        self.assertEqual(result, 6)


if __name__ == "__main__":
    unittest.main()
