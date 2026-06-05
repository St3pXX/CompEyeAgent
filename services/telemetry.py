"""OpenTelemetry instrumentation for CompEye Agent.

Provides:
- Tracer for distributed tracing (coordinator loop, node execution, LLM calls)
- Meter for metrics (run duration, node duration, event counts, LLM call counts)
- Prometheus-compatible /metrics endpoint data

Configuration via environment variables:
- OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector URL (e.g. http://localhost:4317)
- OTEL_SERVICE_NAME: service name (default: compeye-agent)
- COMPETEYE_OTEL_ENABLED: set to "true" to enable OTel (default: disabled for local dev)
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any

# OTel imports — guarded so the app still works without the packages installed.
try:
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False


# ---------------------------------------------------------------------------
# Prometheus registry (always created — used by /metrics endpoint)
# ---------------------------------------------------------------------------
PROM_REGISTRY = CollectorRegistry() if _PROM_AVAILABLE else None

# Prometheus metrics (created at module level, independent of OTel)
if _PROM_AVAILABLE and PROM_REGISTRY is not None:
    _runs_total = Counter(
        "compeye_runs_total",
        "Total analysis runs created",
        ["status"],
        registry=PROM_REGISTRY,
    )
    _run_duration = Histogram(
        "compeye_run_duration_seconds",
        "Run execution duration in seconds",
        ["status"],
        buckets=[5, 10, 30, 60, 120, 300, 600],
        registry=PROM_REGISTRY,
    )
    _node_duration = Histogram(
        "compeye_node_duration_seconds",
        "DAG node execution duration in seconds",
        ["node_key"],
        buckets=[2, 5, 15, 30, 60, 120, 300],
        registry=PROM_REGISTRY,
    )
    _node_retries = Counter(
        "compeye_node_retries_total",
        "Total node retry attempts",
        ["node_key"],
        registry=PROM_REGISTRY,
    )
    _events_total = Counter(
        "compeye_events_total",
        "Total events emitted",
        ["event_type"],
        registry=PROM_REGISTRY,
    )
    _llm_calls_total = Counter(
        "compeye_llm_calls_total",
        "Total LLM API calls",
        ["model", "node_key", "status"],
        registry=PROM_REGISTRY,
    )
    _llm_duration = Histogram(
        "compeye_llm_call_duration_seconds",
        "LLM call latency in seconds",
        ["model", "node_key"],
        buckets=[1, 3, 5, 10, 30, 60, 120],
        registry=PROM_REGISTRY,
    )
    _llm_tokens = Counter(
        "compeye_llm_tokens_total",
        "Total LLM tokens consumed",
        ["model", "node_key", "direction"],
        registry=PROM_REGISTRY,
    )
    _active_runs = Gauge(
        "compeye_active_runs",
        "Currently running analysis runs",
        registry=PROM_REGISTRY,
    )
else:
    _runs_total = None
    _run_duration = None
    _node_duration = None
    _node_retries = None
    _events_total = None
    _llm_calls_total = None
    _llm_duration = None
    _llm_tokens = None
    _active_runs = None


# ---------------------------------------------------------------------------
# OTel initialization
# ---------------------------------------------------------------------------
_otel_enabled = False
_tracer: Any = None
_meter: Any = None

# OTel instruments (only created when OTel is enabled)
_otel_run_duration: Any = None
_otel_node_duration: Any = None
_otel_node_retries: Any = None
_otel_events_total: Any = None
_otel_llm_calls: Any = None
_otel_llm_duration: Any = None
_otel_llm_tokens: Any = None


def init_telemetry() -> bool:
    """Initialize OTel tracing and metrics if COMPETEYE_OTEL_ENABLED=true.

    Returns True if OTel was initialized, False otherwise.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _otel_enabled, _tracer, _meter
    global _otel_run_duration, _otel_node_duration, _otel_node_retries, _otel_events_total
    global _otel_llm_calls, _otel_llm_duration, _otel_llm_tokens

    if _otel_enabled:
        return True

    if not _OTEL_AVAILABLE:
        return False

    if os.getenv("COMPETEYE_OTEL_ENABLED", "").lower() != "true":
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME", "compeye-agent")
    resource = Resource.create({"service.name": service_name})

    # Tracer
    tracer_provider = TracerProvider(resource=resource)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    else:
        span_exporter = ConsoleSpanExporter()
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer("compeye-agent")

    # Meter
    readers = []
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)))
    else:
        readers.append(PeriodicExportingMetricReader(ConsoleSpanExporter()))
    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter("compeye-agent")

    _otel_run_duration = _meter.create_histogram("compeye.run.duration", unit="s", description="Run execution duration")
    _otel_node_duration = _meter.create_histogram("compeye.node.duration", unit="s", description="Node execution duration")
    _otel_node_retries = _meter.create_counter("compeye.node.retries", description="Node retry count")
    _otel_events_total = _meter.create_counter("compeye.events", description="Event count")
    _otel_llm_calls = _meter.create_counter("compeye.llm.calls", description="LLM call count")
    _otel_llm_duration = _meter.create_histogram("compeye.llm.duration", unit="s", description="LLM call latency")
    _otel_llm_tokens = _meter.create_counter("compeye.llm.tokens", description="LLM tokens consumed")

    _otel_enabled = True
    return True


# ---------------------------------------------------------------------------
# Tracing helpers
# ---------------------------------------------------------------------------

@contextmanager
def trace_run(run_id: str):
    """Context manager that creates a tracing span for a full run execution."""
    if _tracer is not None:
        with _tracer.start_as_current_span(
            "run.execute",
            attributes={"run_id": run_id},
        ) as span:
            yield span
    else:
        yield None


@contextmanager
def trace_node(run_id: str, node_key: str, attempt: int = 1):
    """Context manager that creates a tracing span for a single node execution."""
    if _tracer is not None:
        with _tracer.start_as_current_span(
            f"node.{node_key}",
            attributes={"run_id": run_id, "node_key": node_key, "attempt": attempt},
        ) as span:
            yield span
    else:
        yield None


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def record_run_created() -> None:
    if _runs_total is not None:
        _runs_total.labels(status="created").inc()


def record_run_completed(status: str, duration_seconds: float) -> None:
    if _runs_total is not None:
        _runs_total.labels(status=status).inc()
    if _run_duration is not None:
        _run_duration.labels(status=status).observe(duration_seconds)
    if _active_runs is not None:
        _active_runs.dec()
    # OTel
    if _otel_run_duration is not None:
        _otel_run_duration.record(duration_seconds, {"status": status})


def record_run_started() -> None:
    if _active_runs is not None:
        _active_runs.inc()


def record_node_duration(node_key: str, duration_seconds: float) -> None:
    if _node_duration is not None:
        _node_duration.labels(node_key=node_key).observe(duration_seconds)
    if _otel_node_duration is not None:
        _otel_node_duration.record(duration_seconds, {"node_key": node_key})


def record_node_retry(node_key: str) -> None:
    if _node_retries is not None:
        _node_retries.labels(node_key=node_key).inc()
    if _otel_node_retries is not None:
        _otel_node_retries.add(1, {"node_key": node_key})


def record_event(event_type: str) -> None:
    if _events_total is not None:
        _events_total.labels(event_type=event_type).inc()
    if _otel_events_total is not None:
        _otel_events_total.add(1, {"event_type": event_type})


# ---------------------------------------------------------------------------
# LLM call instrumentation
# ---------------------------------------------------------------------------

@contextmanager
def trace_llm_call(
    model: str,
    node_key: str,
    *,
    prompt_length: int | None = None,
):
    """Context manager for tracing an individual LLM API call.

    Usage::

        with trace_llm_call("mimo-v2.5", "collect", prompt_length=1200) as span:
            result = crew.kickoff(inputs=inputs)
            if span:
                span.set_attribute("output_length", len(str(result)))
    """
    if _tracer is not None:
        attrs: dict[str, Any] = {"model": model, "node_key": node_key}
        if prompt_length is not None:
            attrs["prompt_length"] = prompt_length
        with _tracer.start_as_current_span("llm.call", attributes=attrs) as span:
            start = time.monotonic()
            try:
                yield span
            finally:
                duration = time.monotonic() - start
                span.set_attribute("duration_seconds", duration)
                record_llm_call(model, node_key, duration, status="success")
    else:
        start = time.monotonic()
        yield None
        duration = time.monotonic() - start
        record_llm_call(model, node_key, duration, status="success")


def record_llm_call(
    model: str,
    node_key: str,
    duration_seconds: float,
    *,
    status: str = "success",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    """Record an LLM call for both Prometheus and OTel metrics."""
    # Prometheus
    if _llm_calls_total is not None:
        _llm_calls_total.labels(model=model, node_key=node_key, status=status).inc()
    if _llm_duration is not None:
        _llm_duration.labels(model=model, node_key=node_key).observe(duration_seconds)
    if input_tokens is not None and _llm_tokens is not None:
        _llm_tokens.labels(model=model, node_key=node_key, direction="input").inc(input_tokens)
    if output_tokens is not None and _llm_tokens is not None:
        _llm_tokens.labels(model=model, node_key=node_key, direction="output").inc(output_tokens)

    # OTel
    if _otel_llm_calls is not None:
        _otel_llm_calls.add(1, {"model": model, "node_key": node_key, "status": status})
    if _otel_llm_duration is not None:
        _otel_llm_duration.record(duration_seconds, {"model": model, "node_key": node_key})
    if input_tokens is not None and _otel_llm_tokens is not None:
        _otel_llm_tokens.add(input_tokens, {"model": model, "node_key": node_key, "direction": "input"})
    if output_tokens is not None and _otel_llm_tokens is not None:
        _otel_llm_tokens.add(output_tokens, {"model": model, "node_key": node_key, "direction": "output"})


def get_prometheus_metrics() -> bytes:
    """Return Prometheus metrics in text format for /metrics endpoint."""
    if _PROM_AVAILABLE and PROM_REGISTRY is not None:
        return generate_latest(PROM_REGISTRY)
    return b""


def get_prometheus_content_type() -> str:
    if _PROM_AVAILABLE:
        return CONTENT_TYPE_LATEST
    return "text/plain"
