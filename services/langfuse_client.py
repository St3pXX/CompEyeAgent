"""Langfuse observability wiring (self-hosted, opt-in via env vars).

Langfuse is the single observability component (replacing Prometheus/OTel).  It
captures LLM prompts, outputs, token usage, and latency for every litellm call —
graph nodes and web_search alike — since they all flow through litellm.

Enable by setting, in ``.env`` (pointing at the self-hosted Langfuse instance):
    LANGFUSE_HOST=http://your-langfuse-host:3000
    LANGFUSE_PUBLIC_KEY=pk-...
    LANGFUSE_SECRET_KEY=sk-...

If the keys are absent, this is a no-op — the app runs without observability.
"""

from __future__ import annotations

import os

_enabled = False


def init_langfuse() -> bool:
    """Register litellm's Langfuse callback if credentials are configured.

    Returns True if Langfuse was enabled.  Safe to call multiple times.
    """
    global _enabled
    if _enabled:
        return True

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return False

    try:
        import litellm

        # litellm reads LANGFUSE_* from the environment; registering the string
        # callback activates the built-in Langfuse logger for every completion.
        success = list(getattr(litellm, "success_callback", []) or [])
        failure = list(getattr(litellm, "failure_callback", []) or [])
        if "langfuse" not in success:
            success.append("langfuse")
            litellm.success_callback = success
        if "langfuse" not in failure:
            failure.append("langfuse")
            litellm.failure_callback = failure
    except ImportError:
        return False

    _enabled = True
    return True


def is_enabled() -> bool:
    return _enabled
