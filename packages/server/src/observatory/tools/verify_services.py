from __future__ import annotations

from pydantic import BaseModel

from observatory.core.context import GuardedContext
from observatory.core.models import Capability
from observatory.core.tracing import tracer
from observatory.tools.list_mcp_servers import list_mcp_servers

NEEDS = frozenset({Capability.PROM})


class ServiceVerification(BaseModel):
    expected: list[str]
    seen: list[str]
    missing: list[str]
    unexpected: list[str]
    ok: bool


async def verify_services(
    ctx: GuardedContext, expected: list[str], window: str = "24h"
) -> ServiceVerification:
    """Check which expected MCP service names are visible in Prometheus metrics."""
    with tracer().start_as_current_span("tool.verify_services") as span:
        span.set_attribute("tool.name", "verify_services")
        seen_list = await list_mcp_servers(ctx, window=window)
        seen_set = set(seen_list)
        expected_set = set(expected)
        missing = sorted(expected_set - seen_set)
        unexpected = sorted(seen_set - expected_set)
        return ServiceVerification(
            expected=sorted(expected),
            seen=sorted(seen_list),
            missing=missing,
            unexpected=unexpected,
            ok=not missing,
        )
