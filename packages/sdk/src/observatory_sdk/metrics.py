from __future__ import annotations

from enum import StrEnum

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class ToolCallOutcome(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


def new_registry() -> CollectorRegistry:
    return CollectorRegistry()


def build_instruments(registry: CollectorRegistry) -> tuple[Counter, Histogram, Gauge]:
    calls = Counter(
        "mcp_tool_calls_total",
        "Total MCP tool calls.",
        ["service", "tool", "outcome"],
        registry=registry,
    )
    duration = Histogram(
        "mcp_tool_duration_seconds",
        "MCP tool call duration in seconds.",
        ["service", "tool", "outcome"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        registry=registry,
    )
    inflight = Gauge(
        "mcp_tool_inflight",
        "Number of in-flight MCP tool calls.",
        ["service", "tool"],
        registry=registry,
    )
    return calls, duration, inflight


def record_tool_call(
    registry: CollectorRegistry,
    service: str,
    tool: str,
    duration_s: float,
    outcome: ToolCallOutcome,
) -> None:
    calls, duration, _ = build_instruments_cached(registry)
    calls.labels(service=service, tool=tool, outcome=outcome.value).inc()
    duration.labels(service=service, tool=tool, outcome=outcome.value).observe(duration_s)


_INSTRUMENTS_CACHE: dict[int, tuple[Counter, Histogram, Gauge]] = {}


def build_instruments_cached(registry: CollectorRegistry) -> tuple[Counter, Histogram, Gauge]:
    k = id(registry)
    if k not in _INSTRUMENTS_CACHE:
        _INSTRUMENTS_CACHE[k] = build_instruments(registry)
    return _INSTRUMENTS_CACHE[k]
