"""Resilience patterns for CompEye Agent: circuit breaker, timeouts, and degradation.

Provides:
- CircuitBreaker: per-provider failure tracking with automatic open/half-open/closed state
- Node timeout enforcement via concurrent.futures
- Partial result delivery when downstream nodes fail but upstream produced output
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and the call is rejected."""

    def __init__(self, provider: str, cooldown_remaining: float) -> None:
        self.provider = provider
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"Circuit breaker open for provider '{provider}'. "
            f"Cooldown remaining: {cooldown_remaining:.1f}s"
        )


class CircuitBreaker:
    """Per-provider circuit breaker with configurable failure threshold and cooldown.

    States:
    - **closed** (normal): calls pass through; failures are counted.
    - **open** (tripped): calls are rejected immediately with CircuitOpenError.
    - **half_open** (probing): one call is allowed through to test recovery.
      If it succeeds, the breaker closes; if it fails, it reopens.
    """

    def __init__(
        self,
        provider: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.provider = provider
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._state: Literal["closed", "open", "half_open"] = "closed"
        self._failure_count: int = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> Literal["closed", "open", "half_open"]:
        with self._lock:
            if self._state == "open":
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self.cooldown_seconds:
                    self._state = "half_open"
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = "closed"

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker OPEN for provider '%s' after %d failures",
                    self.provider,
                    self._failure_count,
                )

    def check(self) -> None:
        """Raise CircuitOpenError if the breaker is open."""
        state = self.state  # triggers half_open transition if cooldown expired
        if state == "open":
            remaining = self.cooldown_seconds - (time.monotonic() - self._opened_at)
            raise CircuitOpenError(self.provider, max(0, remaining))

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *fn* through the circuit breaker.

        Raises CircuitOpenError if the breaker is open.
        Records success/failure automatically.
        """
        self.check()
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def reset(self) -> None:
        """Manually reset the breaker to closed state."""
        with self._lock:
            self._failure_count = 0
            self._state = "closed"
            self._opened_at = 0.0


# ---------------------------------------------------------------------------
# Global circuit breaker registry
# ---------------------------------------------------------------------------

_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(
    provider: str,
    failure_threshold: int = 5,
    cooldown_seconds: float = 60.0,
) -> CircuitBreaker:
    """Get or create a circuit breaker for *provider*."""
    with _breakers_lock:
        if provider not in _breakers:
            _breakers[provider] = CircuitBreaker(
                provider=provider,
                failure_threshold=failure_threshold,
                cooldown_seconds=cooldown_seconds,
            )
        return _breakers[provider]


# ---------------------------------------------------------------------------
# Node timeout
# ---------------------------------------------------------------------------

def run_with_timeout(
    fn: Callable[..., Any],
    *args: Any,
    timeout_seconds: float | None = None,
    **kwargs: Any,
) -> Any:
    """Run *fn* in a thread with an optional timeout.

    If *timeout_seconds* is None or 0, runs synchronously without timeout.
    Raises TimeoutError if the call exceeds the timeout.
    """
    if not timeout_seconds:
        return fn(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeout:
            future.cancel()
            raise TimeoutError(
                f"Node execution exceeded {timeout_seconds}s timeout"
            ) from None
