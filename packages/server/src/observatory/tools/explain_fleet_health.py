from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from observatory.core.context import GuardedContext
from observatory.core.models import Capability, FleetHealthExplanation
from observatory.core.tracing import tracer
from observatory.rules.abandonment import detect
from observatory.tools.get_fleet_health import get_fleet_health
from observatory.tools.list_mcp_servers import list_mcp_servers

NEEDS = frozenset({Capability.PROM, Capability.LLM})


class _ExplanationLLMOutput(BaseModel):
    overall: Literal["healthy", "degraded", "partial_outage", "unknown"] = Field(
        description="Overall fleet assessment."
    )
    reasons: list[str] = Field(description="Short bullets grounded in the evidence.")
    recommendations: list[str] = Field(description="Concrete next actions for SRE on-call.")


def _deterministic(fleet, abandoned_signals, servers) -> FleetHealthExplanation:
    reasons: list[str] = ["LLM unavailable — deterministic summary"]
    confirmed = sum(1 for s in abandoned_signals if s.status == "confirmed")
    suspected = sum(1 for s in abandoned_signals if s.status == "suspected")
    overall: Literal["healthy", "degraded", "partial_outage", "unknown"]
    if confirmed >= 1:
        overall = "partial_outage"
        reasons.append(
            f"{confirmed} confirmed tool-abandonment signal(s) — agents backed off after errors"
        )
    elif suspected >= 1:
        overall = "degraded"
        reasons.append(
            f"{suspected} suspected abandonment(s) — investigate for benign seasonality vs. real drop"
        )
    elif not servers:
        overall = "unknown"
        reasons.append("No MCP servers scraped in the last window — check Prometheus scrape config")
    else:
        overall = "healthy"
        reasons.append(f"{len(servers)} MCP server(s) healthy")
    recs = [
        "Run detect_tool_abandonment with narrower filters to triage",
        "Check prod-readiness and deploy-intel dashboards for the affected services",
    ]
    return FleetHealthExplanation(
        overall=overall,
        reasons=reasons,
        recommendations=recs,
        evidence={
            "fleet": fleet.model_dump(mode="json"),
            "abandonment_signals": [s.model_dump(mode="json") for s in abandoned_signals],
        },
    )


async def explain_fleet_health(ctx: GuardedContext) -> FleetHealthExplanation:
    """Synthesise a fleet-wide health narrative. LLM-driven with deterministic fallback."""
    with tracer().start_as_current_span("tool.explain_fleet_health") as span:
        span.set_attribute("tool.name", "explain_fleet_health")
        servers = await list_mcp_servers(ctx)
        fleet = await get_fleet_health(ctx)
        abandonment_signals = await detect(ctx.prom)

        await ctx.llm.ensure_ready()
        if ctx.llm.effectively_offline:
            return _deterministic(fleet, abandonment_signals, servers)

        prompt = (
            "Summarise the health of this MCP fleet based on the evidence below. "
            "Produce an overall verdict, reasons (cite specific numbers), and 2-4 concrete "
            "recommendations for SRE on-call. Ground every bullet in evidence.\n\n"
            f"Fleet: {fleet.model_dump_json()}\n"
            f"Abandonment signals: {[s.model_dump(mode='json') for s in abandonment_signals]}"
        )
        try:
            out = await ctx.llm.structured(prompt, response_model=_ExplanationLLMOutput)
        except Exception:
            return _deterministic(fleet, abandonment_signals, servers)

        return FleetHealthExplanation(
            overall=out.overall,
            reasons=out.reasons,
            recommendations=out.recommendations,
            evidence={
                "fleet": fleet.model_dump(mode="json"),
                "abandonment_signals": [s.model_dump(mode="json") for s in abandonment_signals],
            },
        )
