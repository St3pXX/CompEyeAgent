from __future__ import annotations

import os
import sys

os.environ.pop("SSLKEYLOGFILE", None)
for proxy_var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(proxy_var, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")


def create_llm(model_name: str) -> LLM:
    """Create a CrewAI LLM instance configured for the MiMo OpenAI-compatible API.

    This is the simple single-provider factory.  For multi-model fallback,
    use ``create_llm_for_role()`` instead.

    .. deprecated::
        Superseded by :func:`create_llm_client` (litellm-backed ``LLMClient``)
        as part of the LangGraph migration.  Kept while CrewAI agents still exist.
    """
    from crewai import LLM

    litellm_model = model_name
    if not litellm_model.startswith("openai/"):
        litellm_model = f"openai/{litellm_model}"

    return LLM(
        base_url=MIMO_BASE_URL,
        api_key=MIMO_API_KEY,
        model=litellm_model,
        temperature=0.7,
        top_p=0.95,
        max_completion_tokens=2048,
        extra_body={"thinking": {"type": "disabled"}},
    )


def create_llm_client(model_name: str):
    """Create an :class:`~services.llm_client.LLMClient` for the MiMo endpoint.

    litellm-backed replacement for :func:`create_llm`.  For multi-model
    fallback use :func:`create_llm_client_for_role`.
    """
    from services.llm_client import LLMClient

    return LLMClient(
        base_url=MIMO_BASE_URL,
        api_key=MIMO_API_KEY,
        model=model_name,
    )


# ---------------------------------------------------------------------------
# Model registry (multi-provider fallback)
# ---------------------------------------------------------------------------

_model_registry = None


def get_model_registry():
    """Get or create the global ModelRegistry singleton."""
    global _model_registry
    if _model_registry is None:
        from config.model_registry import build_default_registry
        _model_registry = build_default_registry()
    return _model_registry


def create_llm_for_role(role: str):
    """Create a CrewAI LLM for *role* using the model registry with fallback.

    Falls back to ``create_llm()`` if the registry has no providers for *role*.
    """
    registry = get_model_registry()
    providers = registry.get_providers(role)
    if providers:
        return registry.create_llm(role)
    # Fallback: use the legacy single-provider factory
    role_model = ROLE_MODELS.get(role, "mimo-v2.5")
    return create_llm(role_model)


def create_llm_client_for_role(role: str):
    """Create an :class:`LLMClient` for *role* using the registry with fallback.

    litellm-backed replacement for :func:`create_llm_for_role`.  Falls back to
    :func:`create_llm_client` if the registry has no providers for *role*.
    """
    registry = get_model_registry()
    providers = registry.get_providers(role)
    if providers:
        return registry.create_llm_client(role)
    role_model = ROLE_MODELS.get(role, "mimo-v2.5")
    return create_llm_client(role_model)


# Model assignments (backward compatible)
COLLECTOR_MODEL = os.getenv("COLLECTOR_MODEL", "mimo-v2.5")
ANALYZER_MODEL = os.getenv("ANALYZER_MODEL", "mimo-v2.5")
WRITER_MODEL = os.getenv("WRITER_MODEL", "mimo-v2.5")
VERIFIER_MODEL = os.getenv("VERIFIER_MODEL", "mimo-v2.5-pro")

ROLE_MODELS = {
    "collector": COLLECTOR_MODEL,
    "analyzer": ANALYZER_MODEL,
    "writer": WRITER_MODEL,
    "verifier": VERIFIER_MODEL,
}
