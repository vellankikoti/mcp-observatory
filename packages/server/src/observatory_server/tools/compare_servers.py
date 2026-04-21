from __future__ import annotations

import asyncio

from observatory_server.core.context import GuardedContext
from observatory_server.core.models import Capability, ServerComparison
from observatory_server.core.tracing import tracer
from observatory_server.tools._util import _parse_window

NEEDS = frozenset({Capability.PROM})


def _scalar(d: object) -> float | None:
    if isinstance(d, Exception):
        return None
    if not isinstance(d, dict):
        return None
    r = d.get("result") or []
    if not r:
        return None
    try:
        return float(r[0]["value"][1])
    except (KeyError, IndexError, ValueError, TypeError):
        return None


async def compare_servers(
    ctx: GuardedContext,
    service_a: str,
    service_b: str,
    window: str = "1h",
) -> ServerComparison:
    """Compare two MCP services by tool count, error rate, and p99 latency (instant queries)."""
    with tracer().start_as_current_span("tool.compare_servers") as span:
        span.set_attribute("tool.name", "compare_servers")
        span.set_attribute("service_a", service_a)
        span.set_attribute("service_b", service_b)
        span.set_attribute("window", window)
        # validate window early so bad input raises before any network call
        _parse_window(window)

        tools_a_q = f'count(count by (tool)(mcp_tool_calls_total{{service="{service_a}"}}))'
        err_a_q = (
            f'sum(rate(mcp_tool_calls_total{{service="{service_a}",outcome="error"}}[5m])) '
            f'/ sum(rate(mcp_tool_calls_total{{service="{service_a}"}}[5m]))'
        )
        p99_a_q = f'histogram_quantile(0.99, sum by (le)(rate(mcp_tool_duration_seconds_bucket{{service="{service_a}"}}[5m]))) * 1000'

        tools_b_q = f'count(count by (tool)(mcp_tool_calls_total{{service="{service_b}"}}))'
        err_b_q = (
            f'sum(rate(mcp_tool_calls_total{{service="{service_b}",outcome="error"}}[5m])) '
            f'/ sum(rate(mcp_tool_calls_total{{service="{service_b}"}}[5m]))'
        )
        p99_b_q = f'histogram_quantile(0.99, sum by (le)(rate(mcp_tool_duration_seconds_bucket{{service="{service_b}"}}[5m]))) * 1000'

        data = await asyncio.gather(
            ctx.prom.query(tools_a_q),
            ctx.prom.query(err_a_q),
            ctx.prom.query(p99_a_q),
            ctx.prom.query(tools_b_q),
            ctx.prom.query(err_b_q),
            ctx.prom.query(p99_b_q),
            return_exceptions=True,
        )

        return ServerComparison(
            service_a=service_a,
            service_b=service_b,
            window=window,
            tools_a=int(_scalar(data[0]) or 0),
            tools_b=int(_scalar(data[3]) or 0),
            error_rate_a=_scalar(data[1]),
            error_rate_b=_scalar(data[4]),
            p99_latency_ms_a=_scalar(data[2]),
            p99_latency_ms_b=_scalar(data[5]),
        )
