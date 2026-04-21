from __future__ import annotations

from observatory_server.core.context import GuardedContext
from observatory_server.core.models import Capability
from observatory_server.core.tracing import tracer

NEEDS = frozenset({Capability.PROM})


async def list_mcp_servers(ctx: GuardedContext, window: str = "24h") -> list[str]:
    """Return sorted unique `service` labels seen in mcp_tool_calls_total over `window`."""
    with tracer().start_as_current_span("tool.list_mcp_servers") as span:
        span.set_attribute("tool.name", "list_mcp_servers")
        span.set_attribute("window", window)
        promql = f"count by (service)(count_over_time(mcp_tool_calls_total[{window}]))"
        data = await ctx.prom.query(promql)
        services = sorted(
            {
                s.get("metric", {}).get("service", "unknown")
                for s in (data.get("result") or [])
                if s.get("metric", {}).get("service")
            }
        )
        span.set_attribute("services", len(services))
        return services
