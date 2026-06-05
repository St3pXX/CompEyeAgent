"""Tests for services.telemetry — OTel instrumentation and Prometheus metrics."""

import unittest

from services.telemetry import (
    get_prometheus_content_type,
    get_prometheus_metrics,
    init_telemetry,
    record_event,
    record_llm_call,
    record_node_duration,
    record_node_retry,
    record_run_completed,
    record_run_created,
    record_run_started,
    trace_llm_call,
)


class TelemetryTest(unittest.TestCase):
    def test_init_telemetry_returns_false_when_disabled(self) -> None:
        """OTel is disabled by default (COMPETEYE_OTEL_ENABLED not set)."""
        result = init_telemetry()
        self.assertFalse(result)

    def test_prometheus_metrics_endpoint_returns_bytes(self) -> None:
        data = get_prometheus_metrics()
        self.assertIsInstance(data, bytes)

    def test_prometheus_content_type(self) -> None:
        ct = get_prometheus_content_type()
        self.assertIn("text", ct)

    def test_record_run_created_does_not_raise(self) -> None:
        record_run_created()

    def test_record_run_started_does_not_raise(self) -> None:
        record_run_started()

    def test_record_run_completed_does_not_raise(self) -> None:
        record_run_completed("passed", 42.0)

    def test_record_node_duration_does_not_raise(self) -> None:
        record_node_duration("collect", 12.5)

    def test_record_node_retry_does_not_raise(self) -> None:
        record_node_retry("verify")

    def test_record_event_does_not_raise(self) -> None:
        record_event("agent.started")

    def test_prometheus_metrics_contain_registered_metrics(self) -> None:
        """After recording some metrics, the output should contain our metric names."""
        record_run_created()
        record_run_started()
        record_run_completed("passed", 10.0)
        record_node_duration("collect", 5.0)
        record_event("agent.started")

        output = get_prometheus_metrics().decode("utf-8")
        self.assertIn("compeye_runs_total", output)
        self.assertIn("compeye_run_duration_seconds", output)
        self.assertIn("compeye_node_duration_seconds", output)
        self.assertIn("compeye_events_total", output)
        self.assertIn("compeye_active_runs", output)

    def test_record_llm_call_does_not_raise(self) -> None:
        record_llm_call("mimo-v2.5", "collect", 3.5, status="success", input_tokens=100, output_tokens=50)

    def test_record_llm_call_failure(self) -> None:
        record_llm_call("mimo-v2.5", "verify", 1.0, status="failure")

    def test_trace_llm_call_context_manager(self) -> None:
        with trace_llm_call("mimo-v2.5", "collect", prompt_length=500) as span:
            self.assertIsNone(span)  # OTel disabled, span is None

    def test_prometheus_contains_llm_metrics(self) -> None:
        record_llm_call("mimo-v2.5", "collect", 2.0, input_tokens=200, output_tokens=100)
        output = get_prometheus_metrics().decode("utf-8")
        self.assertIn("compeye_llm_calls_total", output)
        self.assertIn("compeye_llm_call_duration_seconds", output)
        self.assertIn("compeye_llm_tokens_total", output)


if __name__ == "__main__":
    unittest.main()
