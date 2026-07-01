"""Web search — MiMo native web search, extracted from CrewAI WebSearchTool.

The collector node calls ``web_search(query)`` directly instead of wrapping it
in a CrewAI tool.  Uses MiMo's OpenAI-compatible completion endpoint with the
collector model to perform a search-and-summarize call.
"""

from __future__ import annotations

import os

from config.settings import COLLECTOR_MODEL, MIMO_API_KEY, MIMO_BASE_URL
from services.llm_client import _normalize_model


def web_search(query: str, *, timeout: int = 30) -> str:
    """Search public web info for *query*, returning a summarized result string.

    Mirrors the behavior of the legacy ``WebSearchTool._run``: a single MiMo
    completion asked to search and return results with source URLs.  Returns an
    error string (prefixed ``搜索失败:``) rather than raising, so callers can
    degrade gracefully.
    """
    import litellm

    try:
        response = litellm.completion(
            model=_normalize_model(COLLECTOR_MODEL),
            messages=[{"role": "user", "content": f"请搜索以下内容并返回结果：{query}"}],
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL,
            temperature=0.7,
            top_p=0.95,
            max_completion_tokens=2048,
            extra_body={"thinking": {"type": "disabled"}},
            timeout=timeout,
        )
        return response.choices[0].message.content or ""
    except Exception as e:  # noqa: BLE001 — surface failure as string, don't crash the node
        return f"搜索失败: {str(e)}"
