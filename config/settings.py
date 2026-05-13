from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


def create_llm(model_name: str) -> ChatOpenAI:
    """Create a ChatOpenAI instance configured for MiMo API."""
    return ChatOpenAI(
        base_url=os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimmo.com/v1"),
        api_key=os.getenv("MIMO_API_KEY", ""),
        model=model_name,
    )


# Model assignments
COLLECTOR_MODEL = os.getenv("COLLECTOR_MODEL", "xiaomi/mimo-v2.5")
ANALYZER_MODEL = os.getenv("ANALYZER_MODEL", "xiaomi/mimo-v2.5")
WRITER_MODEL = os.getenv("WRITER_MODEL", "xiaomi/mimo-v2.5")
VERIFIER_MODEL = os.getenv("VERIFIER_MODEL", "xiaomi/mimo-v2.5-pro")