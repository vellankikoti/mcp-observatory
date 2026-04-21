from __future__ import annotations

from datetime import UTC, datetime

from observatory.core.context import GuardedContext
from observatory.core.models import Capability, TimeSeries
from observatory.core.tracing import tracer
from observatory.tools._util import _parse_window

NEEDS = frozenset({Capability.PROM})


async def get_tool_call_rate(
    ctx: GuardedContext,
    service: str,
    tool: str | None = None,
    window: str = "1h",
) -> TimeSeries:
    """Return call-rate TimeSeries for a service (optionally filtered by tool) over window."""
    with tracer().start_as_current_span("tool.get_tool_call_rate") as span:
        span.set_attribute("tool.name", "get_tool_call_rate")
        span.set_attribute("service", service)
        span.set_attribute("window", window)
        delta = _parse_window(window)
        end = datetime.now(UTC)
        start = end - delta
        step = max(15.0, delta.total_seconds() / 300)
        if tool:
            promql = f'sum(rate(mcp_tool_calls_total{{service="{service}",tool="{tool}"}}[5m]))'
        else:
            promql = f'sum(rate(mcp_tool_calls_total{{service="{service}"}}[5m]))'
        data = await ctx.prom.query_range(promql, start.timestamp(), end.timestamp(), step)
        samples: list[tuple[datetime, float]] = []
        for series in data.get("result") or []:
            for ts, raw in series.get("values", []):
                try:
                    samples.append((datetime.fromtimestamp(float(ts), UTC), float(raw)))
                except (TypeError, ValueError):
                    continue
        return TimeSeries(promql=promql, start=start, end=end, step_s=step, samples=samples)
