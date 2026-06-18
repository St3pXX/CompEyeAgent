"""LLM token telemetry — LiteLLM callback-based token tracking.

Captures input/output token counts from every LiteLLM completion call
and makes them available per-run for cost reporting.
"""

from __future__ import annotations

import contextvars
import threading
from typing import Any

_current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_run_id", default=None
)
_token_metrics: dict[str, dict[str, int]] = {}
_lock = threading.Lock()


def set_current_run_id(run_id: str | None) -> None:
    _current_run_id.set(run_id)


def get_current_run_id() -> str | None:
    return _current_run_id.get()


def _success_callback(
    kwargs: dict[str, Any],
    completion_response: Any,
    start_time: Any,
    end_time: Any,
) -> None:
    run_id = get_current_run_id()
    if not run_id:
        return

    usage = None
    if hasattr(completion_response, "usage") and completion_response.usage:
        usage = completion_response.usage
    elif isinstance(completion_response, dict) and "usage" in completion_response:
        usage = completion_response["usage"]

    if not usage:
        return

    input_tokens = getattr(usage, "prompt_tokens", 0) if hasattr(usage, "prompt_tokens") else usage.get("prompt_tokens", 0)
    output_tokens = getattr(usage, "completion_tokens", 0) if hasattr(usage, "completion_tokens") else usage.get("completion_tokens", 0)

    if not input_tokens and not output_tokens:
        return

    with _lock:
        if run_id not in _token_metrics:
            _token_metrics[run_id] = {"input_tokens": 0, "output_tokens": 0}
        _token_metrics[run_id]["input_tokens"] += input_tokens
        _token_metrics[run_id]["output_tokens"] += output_tokens


def get_token_metrics(run_id: str) -> dict[str, int]:
    with _lock:
        return _token_metrics.pop(run_id, {"input_tokens": 0, "output_tokens": 0})


def register_litellm_callback() -> None:
    try:
        import litellm

        callbacks = list(getattr(litellm, "success_callback", []) or [])
        if _success_callback not in callbacks:
            callbacks.append(_success_callback)
            litellm.success_callback = callbacks
    except ImportError:
        pass
