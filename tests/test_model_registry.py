"""Tests for config.model_registry — model provider registry and fallback."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.model_registry import (
    ModelProvider,
    ModelRegistry,
    _build_from_env,
    _build_from_yaml,
)


class ModelProviderTest(unittest.TestCase):
    def test_defaults(self) -> None:
        p = ModelProvider(name="test", base_url="http://x", api_key="k", model_name="m")
        self.assertEqual(p.priority, 1)
        self.assertTrue(p.enabled)
        self.assertEqual(p.temperature, 0.7)


class ModelRegistryTest(unittest.TestCase):
    def test_register_and_get_providers(self) -> None:
        r = ModelRegistry()
        r.register("collector", ModelProvider(name="a", base_url="u", api_key="k", model_name="m1", priority=1))
        r.register("collector", ModelProvider(name="b", base_url="u", api_key="k", model_name="m2", priority=2))
        providers = r.get_providers("collector")
        self.assertEqual(len(providers), 2)
        self.assertEqual(providers[0].priority, 1)
        self.assertEqual(providers[1].priority, 2)

    def test_sorted_by_priority(self) -> None:
        r = ModelRegistry()
        r.register("x", ModelProvider(name="b", base_url="u", api_key="k", model_name="m2", priority=2))
        r.register("x", ModelProvider(name="a", base_url="u", api_key="k", model_name="m1", priority=1))
        providers = r.get_providers("x")
        self.assertEqual(providers[0].name, "a")
        self.assertEqual(providers[1].name, "b")

    def test_filters_disabled(self) -> None:
        r = ModelRegistry()
        r.register("x", ModelProvider(name="a", base_url="u", api_key="k", model_name="m1", enabled=True))
        r.register("x", ModelProvider(name="b", base_url="u", api_key="k", model_name="m2", enabled=False))
        self.assertEqual(len(r.get_providers("x")), 1)

    def test_empty_role_returns_empty(self) -> None:
        r = ModelRegistry()
        self.assertEqual(r.get_providers("nonexistent"), [])


class BuildFromEnvTest(unittest.TestCase):
    @patch.dict("os.environ", {
        "MIMO_BASE_URL": "http://mimo.test",
        "MIMO_API_KEY": "key1",
        "COLLECTOR_MODEL": "mimo-v2.5",
        "ANALYZER_MODEL": "mimo-v2.5",
        "WRITER_MODEL": "mimo-v2.5",
        "VERIFIER_MODEL": "mimo-v2.5-pro",
    }, clear=False)
    def test_builds_primary_only(self) -> None:
        r = _build_from_env()
        self.assertEqual(len(r.get_providers("collector")), 1)
        self.assertEqual(r.get_providers("collector")[0].name, "mimo")

    @patch.dict("os.environ", {
        "MIMO_BASE_URL": "http://mimo.test",
        "MIMO_API_KEY": "key1",
        "COLLECTOR_MODEL": "mimo-v2.5",
        "ANALYZER_MODEL": "mimo-v2.5",
        "WRITER_MODEL": "mimo-v2.5",
        "VERIFIER_MODEL": "mimo-v2.5-pro",
        "FALLBACK_PROVIDER": "openai",
        "FALLBACK_BASE_URL": "http://openai.test",
        "FALLBACK_API_KEY": "key2",
        "FALLBACK_MODEL": "gpt-4o-mini",
    }, clear=False)
    def test_builds_with_fallback(self) -> None:
        r = _build_from_env()
        providers = r.get_providers("collector")
        self.assertEqual(len(providers), 2)
        self.assertEqual(providers[0].name, "mimo")
        self.assertEqual(providers[1].name, "openai")
        self.assertEqual(providers[1].model_name, "gpt-4o-mini")


class BuildFromYamlTest(unittest.TestCase):
    def test_builds_from_yaml(self) -> None:
        yaml_content = """
collector:
  - provider: mimo
    base_url: http://mimo.test
    api_key: key1
    model: mimo-v2.5
    priority: 1
  - provider: openai
    base_url: http://openai.test
    api_key: key2
    model: gpt-4o-mini
    priority: 2
verifier:
  - provider: mimo
    base_url: http://mimo.test
    api_key: key1
    model: mimo-v2.5-pro
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(yaml_content)
            f.flush()
            r = _build_from_yaml(f.name)

        self.assertEqual(len(r.get_providers("collector")), 2)
        self.assertEqual(len(r.get_providers("verifier")), 1)
        self.assertEqual(r.get_providers("collector")[1].model_name, "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
