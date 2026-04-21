from __future__ import annotations

from datetime import UTC, datetime

from observatory.core.context import GuardedContext
from observatory.core.models import Capability, TimeSeries
from observatory.core.tracing import tracer
from observatory.tools._util import _parse_window

NEEDS = frozenset({Capability.PROM})


async def get_tool_latency_p99(
    ctx: GuardedContext,
    service: str,
    tool: str | None = None,
    window: str = "1h",
) -> TimeSeries:
    """Return p99 latency TimeSeries (seconds) for a service over window via histogram_quantile."""
    with tracer().start_as_current_span("tool.get_tool_latency_p99") as span:
        span.set_attribute("tool.name", "get_tool_latency_p99")
        span.set_attribute("service", service)
        span.set_attribute("window", window)
        delta = _parse_window(window)
        end = datetime.now(UTC)
        start = end - delta
        step = max(15.0, delta.total_seconds() / 300)
        tool_clause = f',tool="{tool}"' if tool else ""
        promql = (
            f"histogram_quantile(0.99, sum by (le)("
            f'rate(mcp_tool_duration_seconds_bucket{{service="{service}"{tool_clause}}}[5m])))'
        )
        data = await ctx.prom.query_range(promql, start.timestamp(), end.timestamp(), step)
        samples: list[tuple[datetime, float]] = []
        for series in data.get("result") or []:
            for ts, raw in series.get("values", []):
                try:
                    samples.append((datetime.fromtimestamp(float(ts), UTC), float(raw)))
                except (TypeError, ValueError):
                    continue
        return TimeSeries(promql=promql, start=start, end=end, step_s=step, samples=samples)
