"""Tests for the litellm-backed LLM wrapper (services.llm_client) and factories.

These mock ``litellm.completion`` so no network/API key is needed.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

from services.llm_client import LLMClient, LLMResult, _normalize_model


def _fake_response(text: str, prompt_tokens: int = 12, completion_tokens: int = 34):
    """Build an object shaped like a litellm completion response."""
    message = types.SimpleNamespace(content=text)
    choice = types.SimpleNamespace(message=message)
    usage = types.SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return types.SimpleNamespace(choices=[choice], usage=usage)


class NormalizeModelTest(unittest.TestCase):
    def test_adds_openai_prefix(self):
        self.assertEqual(_normalize_model("mimo-v2.5"), "openai/mimo-v2.5")

    def test_keeps_existing_prefix(self):
        self.assertEqual(_normalize_model("openai/gpt-4o"), "openai/gpt-4o")


class LLMClientTest(unittest.TestCase):
    def _client(self):
        return LLMClient(base_url="https://x/v1", api_key="k", model="mimo-v2.5")

    def test_single_prompt_returns_text_and_usage(self):
        fake = mock.Mock(return_value=_fake_response("hello", 12, 34))
        with mock.patch.dict(sys.modules, {"litellm": types.SimpleNamespace(completion=fake)}):
            result = self._client()("分析竞品")
        self.assertIsInstance(result, LLMResult)
        self.assertEqual(result.text, "hello")
        self.assertEqual(result.input_tokens, 12)
        self.assertEqual(result.output_tokens, 34)
        # messages built from the single prompt
        called_messages = fake.call_args.kwargs["messages"]
        self.assertEqual(called_messages, [{"role": "user", "content": "分析竞品"}])
        self.assertEqual(fake.call_args.kwargs["model"], "openai/mimo-v2.5")

    def test_system_plus_prompt(self):
        fake = mock.Mock(return_value=_fake_response("ok"))
        with mock.patch.dict(sys.modules, {"litellm": types.SimpleNamespace(completion=fake)}):
            self._client()("问题", system="你是分析师")
        called_messages = fake.call_args.kwargs["messages"]
        self.assertEqual(called_messages[0], {"role": "system", "content": "你是分析师"})
        self.assertEqual(called_messages[1], {"role": "user", "content": "问题"})

    def test_explicit_messages_passthrough(self):
        fake = mock.Mock(return_value=_fake_response("ok"))
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
        with mock.patch.dict(sys.modules, {"litellm": types.SimpleNamespace(completion=fake)}):
            self._client()(messages=msgs)
        self.assertEqual(fake.call_args.kwargs["messages"], msgs)

    def test_requires_prompt_or_messages(self):
        with self.assertRaises(ValueError):
            self._client()()

    def test_missing_usage_defaults_to_zero(self):
        resp = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="t"))],
            usage=None,
        )
        fake = mock.Mock(return_value=resp)
        with mock.patch.dict(sys.modules, {"litellm": types.SimpleNamespace(completion=fake)}):
            result = self._client()("q")
        self.assertEqual((result.input_tokens, result.output_tokens), (0, 0))


class FactoryTest(unittest.TestCase):
    def test_create_llm_client_returns_client(self):
        from config.settings import create_llm_client

        client = create_llm_client("mimo-v2.5")
        self.assertIsInstance(client, LLMClient)
        self.assertEqual(client.model, "mimo-v2.5")

    def test_registry_create_llm_client(self):
        from config.model_registry import ModelProvider, ModelRegistry

        registry = ModelRegistry()
        registry.register("collector", ModelProvider(
            name="mimo", base_url="https://x/v1", api_key="k", model_name="mimo-v2.5",
        ))
        client = registry.create_llm_client("collector")
        self.assertIsInstance(client, LLMClient)
        self.assertEqual(client.model, "mimo-v2.5")

    def test_role_factory_falls_back_without_providers(self):
        from config.settings import create_llm_client_for_role

        client = create_llm_client_for_role("collector")
        self.assertIsInstance(client, LLMClient)


if __name__ == "__main__":
    unittest.main()
