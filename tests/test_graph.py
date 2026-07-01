"""Tests for the LangGraph analysis graph walk logic.

LLM calls (create_llm_client), web_search, and verification_issues are mocked,
so no network/API key is needed.  Focus is on graph routing:
  - normal path: collect -> analyze -> write -> verify -> END (passes)
  - failure path: verify fails once -> rewrite -> verify -> END
  - persistent failure: rewrite doesn't loop forever (MAX_RETRIES honored)
"""

from __future__ import annotations

import unittest
from unittest import mock

from graph.build import build_graph
from graph.state import AnalysisState
from models.schema import CompetitorInput


def _input():
    return CompetitorInput(
        productName="飞书",
        competitors=["钉钉", "企业微信"],
        dimensions=[{"name": "定价", "indicators": ["免费套餐"]}],
        analysisType="SWOT",
    )


class _FakeClient:
    """Returns a canned text tagged by the model, records call order."""

    calls: list[str] = []

    def __init__(self, model):
        self.model = model

    def __call__(self, prompt=None, *, messages=None, system=None):
        _FakeClient.calls.append(self.model)
        from services.llm_client import LLMResult
        return LLMResult(text=f"[{self.model}] output", input_tokens=1, output_tokens=1)


def _run_graph(issues_sequence):
    """Run the graph with mocks; issues_sequence controls verification_issues per call."""
    _FakeClient.calls = []
    seq = list(issues_sequence)

    def fake_issues(report, verifier_result):
        return seq.pop(0) if seq else []

    state: AnalysisState = {
        "input_data": _input(),
        "evidence_index": "none",
        "allow_retry": True,
        "run_id": "test-run",
        "retry_count": 0,
    }

    with mock.patch("graph.nodes.create_llm_client", _FakeClient), \
         mock.patch("graph.nodes.web_search", return_value="search result"), \
         mock.patch("graph.nodes.verification_issues", side_effect=fake_issues):
        graph = build_graph()
        return graph.invoke(state)


class GraphWalkTest(unittest.TestCase):
    def test_normal_path_passes(self):
        # verify passes first time (no issues)
        result = _run_graph([[]])
        self.assertTrue(result["passed"])
        self.assertFalse(result.get("retried", False))
        self.assertIn("collect_raw", result)
        self.assertIn("analyze_findings", result)
        self.assertIn("report", result)
        self.assertIn("verifier_result", result)
        # collect, analyze, write, verify — one call each
        self.assertEqual(_FakeClient.calls.count("mimo-v2.5"), 3)  # collect/analyze/write

    def test_failure_triggers_one_rewrite_then_passes(self):
        # first verify fails, rewrite, second verify passes
        result = _run_graph([["缺少来源标注"], []])
        self.assertTrue(result["passed"])
        self.assertTrue(result["retried"])
        self.assertEqual(result["retry_count"], 1)

    def test_persistent_failure_stops_after_max_retries(self):
        # verify always fails; must not loop forever, ends with passed=False
        result = _run_graph([["issue"], ["issue"], ["issue"], ["issue"]])
        self.assertFalse(result["passed"])
        self.assertTrue(result["retried"])
        self.assertEqual(result["retry_count"], 1)  # MAX_RETRIES == 1

    def test_allow_retry_false_skips_rewrite(self):
        _FakeClient.calls = []
        state: AnalysisState = {
            "input_data": _input(),
            "allow_retry": False,
            "run_id": "r",
            "retry_count": 0,
        }
        with mock.patch("graph.nodes.create_llm_client", _FakeClient), \
             mock.patch("graph.nodes.web_search", return_value="s"), \
             mock.patch("graph.nodes.verification_issues", return_value=["issue"]):
            result = build_graph().invoke(state)
        self.assertFalse(result["passed"])
        self.assertFalse(result.get("retried", False))


if __name__ == "__main__":
    unittest.main()
