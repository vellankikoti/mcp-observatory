from __future__ import annotations

from observatory_server.core.context import GuardedContext
from observatory_server.core.models import AbandonmentSignal, Capability
from observatory_server.core.tracing import tracer
from observatory_server.rules.abandonment import AbandonmentThresholds, detect

NEEDS = frozenset({Capability.PROM})


async def detect_tool_abandonment(
    ctx: GuardedContext,
    service: str | None = None,
    tool: str | None = None,
    drop_pct: float = 80.0,
    baseline_min_rate: float = 0.1,
    error_rate_floor: float = 0.01,
) -> list[AbandonmentSignal]:
    """Detect tools that agents may have silently stopped using."""
    with tracer().start_as_current_span("tool.detect_tool_abandonment") as span:
        span.set_attribute("tool.name", "detect_tool_abandonment")
        if service:
            span.set_attribute("service", service)
        if tool:
            span.set_attribute("tool", tool)
        thresholds = AbandonmentThresholds(
            drop_pct=drop_pct,
            baseline_min_rate=baseline_min_rate,
            error_rate_floor=error_rate_floor,
        )
        signals = await detect(ctx.prom, service=service, tool=tool, thresholds=thresholds)
        span.set_attribute("signals", len(signals))
        return signals
