from __future__ import annotations

from observatory_sdk.tracing import tracer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_tracer_emits_span() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    sdk_tracer = provider.get_tracer("mcp_observatory_sdk")
    with sdk_tracer.start_as_current_span("test.span"):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.span"


def test_tracer_returns_tracer_instance() -> None:
    t = tracer()
    assert t is not None
    # Should be able to start a span without error
    with t.start_as_current_span("noop.span"):
        pass
