from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from observatory_server.core.context import GuardedContext
from observatory_server.core.models import Capability, FleetHealth, ServerHealth
from observatory_server.core.tracing import tracer
from observatory_server.rules.abandonment import detect
from observatory_server.tools.list_mcp_servers import list_mcp_servers

NEEDS = frozenset({Capability.PROM})


async def get_fleet_health(ctx: GuardedContext, window: str = "24h") -> FleetHealth:
    """Aggregate fleet-wide health: per-server counts of healthy/degraded/abandoned tools."""
    with tracer().start_as_current_span("tool.get_fleet_health") as span:
        span.set_attribute("tool.name", "get_fleet_health")
        services = await list_mcp_servers(ctx, window=window)
        # Fetch abandonment signals fleet-wide
        signals = await detect(ctx.prom)

        servers: list[ServerHealth] = []
        for service in services:
            # Per-service tool count
            tools_data = await ctx.prom.query(
                f'count(count by (tool)(mcp_tool_calls_total{{service="{service}"}}))'
            )
            total_tools = (
                int(float(tools_data.get("result", [{}])[0].get("value", [0, "0"])[1]))
                if tools_data.get("result")
                else 0
            )

            # Per-service error-rate (instant)
            err_data = await ctx.prom.query(
                f'sum(rate(mcp_tool_calls_total{{service="{service}",outcome="error"}}[5m])) '
                f'/ sum(rate(mcp_tool_calls_total{{service="{service}"}}[5m]))'
            )
            error_rate = None
            if err_data.get("result"):
                with contextlib.suppress(KeyError, IndexError, ValueError, TypeError):
                    error_rate = float(err_data["result"][0]["value"][1])

            # Per-service p99 latency (instant, seconds → ms)
            p99_data = await ctx.prom.query(
                f"histogram_quantile(0.99, sum by (le)("
                f'rate(mcp_tool_duration_seconds_bucket{{service="{service}"}}[5m]))) * 1000'
            )
            p99 = None
            if p99_data.get("result"):
                with contextlib.suppress(KeyError, IndexError, ValueError, TypeError):
                    p99 = float(p99_data["result"][0]["value"][1])

            svc_signals = [s for s in signals if s.service == service]
            abandoned = len(svc_signals)
            degraded = sum(1 for s in svc_signals if s.status == "suspected")
            confirmed = sum(1 for s in svc_signals if s.status == "confirmed")
            healthy = max(0, total_tools - abandoned - degraded)

            servers.append(
                ServerHealth(
                    service=service,
                    total_tools=total_tools,
                    healthy_count=healthy,
                    degraded_count=degraded,
                    abandoned_count=confirmed,
                    p99_latency_ms=p99,
                    error_rate=error_rate,
                )
            )

        span.set_attribute("servers", len(servers))
        return FleetHealth(servers=servers, last_updated=datetime.now(UTC))
