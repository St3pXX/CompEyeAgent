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

from crewai import LLM
from dotenv import load_dotenv

load_dotenv()

MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")


def create_llm(model_name: str) -> LLM:
    """Create a CrewAI LLM instance configured for the MiMo OpenAI-compatible API."""
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


# Model assignments
COLLECTOR_MODEL = os.getenv("COLLECTOR_MODEL", "mimo-v2.5")
ANALYZER_MODEL = os.getenv("ANALYZER_MODEL", "mimo-v2.5")
WRITER_MODEL = os.getenv("WRITER_MODEL", "mimo-v2.5")
VERIFIER_MODEL = os.getenv("VERIFIER_MODEL", "mimo-v2.5-pro")
