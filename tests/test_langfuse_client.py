"""Tests for services.langfuse_client — litellm Langfuse callback wiring.

litellm is mocked; no network or real Langfuse instance is needed.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

import services.langfuse_client as lf


class LangfuseClientTest(unittest.TestCase):
    def setUp(self):
        # Reset module-level enabled flag between tests.
        lf._enabled = False

    def test_noop_without_keys(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(lf.init_langfuse())
            self.assertFalse(lf.is_enabled())

    def test_registers_callback_with_keys(self):
        fake_litellm = types.SimpleNamespace(success_callback=[], failure_callback=[])
        env = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch.dict(sys.modules, {"litellm": fake_litellm}):
            self.assertTrue(lf.init_langfuse())
            self.assertIn("langfuse", fake_litellm.success_callback)
            self.assertIn("langfuse", fake_litellm.failure_callback)
            self.assertTrue(lf.is_enabled())

    def test_idempotent(self):
        fake_litellm = types.SimpleNamespace(success_callback=[], failure_callback=[])
        env = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch.dict(sys.modules, {"litellm": fake_litellm}):
            lf.init_langfuse()
            lf.init_langfuse()
            # only one 'langfuse' entry despite two calls
            self.assertEqual(fake_litellm.success_callback.count("langfuse"), 1)


if __name__ == "__main__":
    unittest.main()
