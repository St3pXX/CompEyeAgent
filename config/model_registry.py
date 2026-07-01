"""Model registry with priority-based fallback for CompEye Agent.

Supports multiple LLM providers per agent role.  When the primary provider
fails (circuit breaker open, rate limit, 5xx), the registry automatically
falls back to the next provider in priority order.

Configuration (environment variables):
    MIMO_BASE_URL / MIMO_API_KEY / COLLECTOR_MODEL / ...  — primary provider (backward compatible)
    FALLBACK_PROVIDER / FALLBACK_BASE_URL / FALLBACK_API_KEY / FALLBACK_MODEL  — optional fallback

Or YAML config (config/model_config.yaml) for richer multi-provider chains.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

from services.resilience import CircuitBreaker, CircuitOpenError, get_circuit_breaker


@dataclass
class ModelProvider:
    """A single model provider configuration."""
    name: str                   # "mimo", "openai", "anthropic"
    base_url: str
    api_key: str
    model_name: str
    priority: int = 1           # 1 = primary, 2 = first fallback, ...
    enabled: bool = True
    temperature: float = 0.7
    top_p: float = 0.95
    max_completion_tokens: int = 2048
    extra_body: dict[str, Any] = field(default_factory=lambda: {"thinking": {"type": "disabled"}})


class ModelRegistry:
    """Registry of model providers per agent role, with fallback ordering.

    Usage::

        registry = ModelRegistry()
        registry.register("collector", ModelProvider(...))
        registry.register("collector", ModelProvider(..., priority=2))

        llm = registry.create_llm("collector")  # tries providers in priority order
    """

    def __init__(self) -> None:
        self._providers: dict[str, list[ModelProvider]] = {}

    def register(self, role: str, provider: ModelProvider) -> None:
        """Register a provider for *role*.  Providers are sorted by priority."""
        if role not in self._providers:
            self._providers[role] = []
        self._providers[role].append(provider)
        self._providers[role].sort(key=lambda p: p.priority)

    def get_providers(self, role: str) -> list[ModelProvider]:
        """Return providers for *role*, sorted by priority, filtered by enabled."""
        return [p for p in self._providers.get(role, []) if p.enabled]

    def create_llm(self, role: str) -> Any:
        """Create a CrewAI LLM instance, trying providers in priority order.

        Skips providers whose circuit breaker is open.
        Raises RuntimeError if all providers are exhausted.
        """
        providers = self.get_providers(role)
        if not providers:
            raise RuntimeError(f"No model providers registered for role '{role}'")

        errors: list[str] = []
        for provider in providers:
            cb = get_circuit_breaker(provider.name)
            try:
                cb.check()
            except CircuitOpenError as e:
                errors.append(str(e))
                continue

            try:
                llm = _create_llm_from_provider(provider)
                return llm
            except Exception as e:
                cb.record_failure()
                errors.append(f"{provider.name}/{provider.model_name}: {e}")
                continue

        raise RuntimeError(
            f"All model providers failed for role '{role}':\n" + "\n".join(errors)
        )

    def create_llm_client(self, role: str) -> Any:
        """Create an :class:`LLMClient`, trying providers in priority order.

        litellm-backed replacement for :meth:`create_llm`.  Skips providers
        whose circuit breaker is open; raises RuntimeError if all are exhausted.
        """
        providers = self.get_providers(role)
        if not providers:
            raise RuntimeError(f"No model providers registered for role '{role}'")

        errors: list[str] = []
        for provider in providers:
            cb = get_circuit_breaker(provider.name)
            try:
                cb.check()
            except CircuitOpenError as e:
                errors.append(str(e))
                continue

            try:
                return _create_llm_client_from_provider(provider)
            except Exception as e:
                cb.record_failure()
                errors.append(f"{provider.name}/{provider.model_name}: {e}")
                continue

        raise RuntimeError(
            f"All model providers failed for role '{role}':\n" + "\n".join(errors)
        )


def _create_llm_client_from_provider(provider: ModelProvider) -> Any:
    """Create an :class:`LLMClient` from a ModelProvider config."""
    from services.llm_client import LLMClient

    return LLMClient(
        base_url=provider.base_url,
        api_key=provider.api_key,
        model=provider.model_name,
        temperature=provider.temperature,
        top_p=provider.top_p,
        max_completion_tokens=provider.max_completion_tokens,
        extra_body=provider.extra_body,
    )
    """Create a CrewAI LLM instance from a ModelProvider config."""
    from crewai import LLM

    litellm_model = provider.model_name
    if not litellm_model.startswith("openai/"):
        litellm_model = f"openai/{litellm_model}"

    return LLM(
        base_url=provider.base_url,
        api_key=provider.api_key,
        model=litellm_model,
        temperature=provider.temperature,
        top_p=provider.top_p,
        max_completion_tokens=provider.max_completion_tokens,
        extra_body=provider.extra_body,
    )


def build_default_registry() -> ModelRegistry:
    """Build a registry from environment variables (backward compatible).

    Supports:
    - Primary model via MIMO_BASE_URL / MIMO_API_KEY / {ROLE}_MODEL
    - Optional fallback via FALLBACK_PROVIDER / FALLBACK_BASE_URL / FALLBACK_API_KEY / FALLBACK_MODEL
    - Optional YAML config via COMPETEYE_MODEL_CONFIG env var pointing to a YAML file
    """
    yaml_path = os.getenv("COMPETEYE_MODEL_CONFIG")
    if yaml_path:
        return _build_from_yaml(yaml_path)

    return _build_from_env()


def _build_from_env() -> ModelRegistry:
    """Build registry from environment variables."""
    registry = ModelRegistry()

    base_url = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    api_key = os.getenv("MIMO_API_KEY", "")

    role_models = {
        "collector": os.getenv("COLLECTOR_MODEL", "mimo-v2.5"),
        "analyzer": os.getenv("ANALYZER_MODEL", "mimo-v2.5"),
        "writer": os.getenv("WRITER_MODEL", "mimo-v2.5"),
        "verifier": os.getenv("VERIFIER_MODEL", "mimo-v2.5-pro"),
    }

    for role, model in role_models.items():
        registry.register(role, ModelProvider(
            name="mimo",
            base_url=base_url,
            api_key=api_key,
            model_name=model,
            priority=1,
        ))

    # Optional fallback provider
    fallback_url = os.getenv("FALLBACK_BASE_URL")
    fallback_key = os.getenv("FALLBACK_API_KEY")
    fallback_model = os.getenv("FALLBACK_MODEL")
    fallback_name = os.getenv("FALLBACK_PROVIDER", "fallback")

    if fallback_url and fallback_key and fallback_model:
        for role in role_models:
            registry.register(role, ModelProvider(
                name=fallback_name,
                base_url=fallback_url,
                api_key=fallback_key,
                model_name=fallback_model,
                priority=2,
            ))

    return registry


def _build_from_yaml(path: str) -> ModelRegistry:
    """Build registry from a YAML config file.

    Expected format::

        collector:
          - provider: mimo
            base_url: https://api.xiaomimimo.com/v1
            api_key: sk-xxx
            model: mimo-v2.5
            priority: 1
          - provider: openai
            base_url: https://api.openai.com/v1
            api_key: sk-yyy
            model: gpt-4o-mini
            priority: 2
    """
    registry = ModelRegistry()

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for role, providers in config.items():
        for entry in providers:
            registry.register(role, ModelProvider(
                name=entry.get("provider", role),
                base_url=entry["base_url"],
                api_key=entry["api_key"],
                model_name=entry["model"],
                priority=entry.get("priority", 1),
                enabled=entry.get("enabled", True),
                temperature=entry.get("temperature", 0.7),
                top_p=entry.get("top_p", 0.95),
                max_completion_tokens=entry.get("max_completion_tokens", 2048),
            ))

    return registry
