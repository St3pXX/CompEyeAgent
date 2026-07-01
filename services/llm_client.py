"""LLM client — litellm-backed callable wrapper (replaces CrewAI LLM).

Provides a thin, provider-agnostic callable that takes chat messages (or a
single prompt) and returns generated text plus token usage.  This replaces the
CrewAI ``LLM`` object that used to be returned by ``config.settings.create_llm``
— the graph nodes call this directly instead of running a single-node Crew.

Token accounting still flows through ``services.llm_telemetry`` via litellm's
global success callback, so per-run Cost reporting is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Default generation parameters, matching the legacy CrewAI LLM config
# (see the old config/settings.create_llm and model_registry.ModelProvider).
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.95
DEFAULT_MAX_COMPLETION_TOKENS = 2048
DEFAULT_EXTRA_BODY: dict[str, Any] = {"thinking": {"type": "disabled"}}


@dataclass
class LLMResult:
    """Result of a single LLM completion call."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def _normalize_model(model_name: str) -> str:
    """Prefix the model with ``openai/`` for litellm's OpenAI-compatible route."""
    if model_name.startswith("openai/"):
        return model_name
    return f"openai/{model_name}"


class LLMClient:
    """Callable litellm wrapper for a single provider configuration.

    Usage::

        client = LLMClient(base_url=..., api_key=..., model="mimo-v2.5")
        result = client("请分析竞品定价")                      # single prompt
        result = client(messages=[{"role": "user", ...}])      # explicit messages
        print(result.text, result.input_tokens, result.output_tokens)
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        extra_body: dict[str, Any] | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_completion_tokens = max_completion_tokens
        self.extra_body = extra_body if extra_body is not None else dict(DEFAULT_EXTRA_BODY)
        self.timeout = timeout

    def __call__(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, str]] | None = None,
        system: str | None = None,
    ) -> LLMResult:
        """Run a completion and return text + token usage.

        Provide either ``prompt`` (optionally with ``system``) or an explicit
        ``messages`` list.  Token counts are also captured by the litellm
        success callback in ``llm_telemetry`` for per-run Cost tracking.
        """
        import litellm

        if messages is None:
            if prompt is None:
                raise ValueError("LLMClient requires either 'prompt' or 'messages'")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

        response = litellm.completion(
            model=_normalize_model(self.model),
            messages=messages,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            top_p=self.top_p,
            max_completion_tokens=self.max_completion_tokens,
            extra_body=self.extra_body,
            timeout=self.timeout,
        )

        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        input_tokens = 0
        output_tokens = 0
        if usage is not None:
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0

        return LLMResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens)
