from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from observatory_server.core.context import ObservatoryContext
from observatory_server.core.models import AbandonmentSignal, Capability, FleetHealth, ServerHealth
from observatory_server.tools.explain_fleet_health import (
    NEEDS,
    _ExplanationLLMOutput,
    explain_fleet_health,
)


def _make_offline_llm() -> MagicMock:
    llm = MagicMock()
    llm.ensure_ready = AsyncMock()
    llm.effectively_offline = True
    return llm


def _make_online_llm(output: _ExplanationLLMOutput) -> MagicMock:
    llm = MagicMock()
    llm.ensure_ready = AsyncMock()
    llm.effectively_offline = False
    llm.structured = AsyncMock(return_value=output)
    return llm


def _empty_prom() -> MagicMock:
    prom = MagicMock()
    prom.query = AsyncMock(return_value={"result": []})
    return prom


def _fleet_empty() -> FleetHealth:
    return FleetHealth(servers=[], last_updated=datetime.now(UTC))


def _fleet_one_server() -> FleetHealth:
    srv = ServerHealth(
        service="svc-a",
        total_tools=5,
        healthy_count=5,
        degraded_count=0,
        abandoned_count=0,
    )
    return FleetHealth(servers=[srv], last_updated=datetime.now(UTC))


def _signal(status: str) -> AbandonmentSignal:
    return AbandonmentSignal(
        service="svc-a",
        tool="my_tool",
        status=status,  # type: ignore[arg-type]
        baseline_rate=1.0,
        current_rate=0.0,
        drop_pct=100.0,
    )


def test_needs_is_prom_and_llm() -> None:
    assert frozenset({Capability.PROM, Capability.LLM}) == NEEDS


@pytest.mark.asyncio
async def test_offline_returns_deterministic_healthy() -> None:
    """Offline LLM + no signals + 1 server → overall='healthy'."""
    prom = _empty_prom()
    llm = _make_offline_llm()
    ctx = ObservatoryContext(prom=prom, llm=llm).guard(needs=NEEDS)

    with (
        patch(
            "observatory_server.tools.explain_fleet_health.list_mcp_servers",
            AsyncMock(return_value=["svc-a"]),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.get_fleet_health",
            AsyncMock(return_value=_fleet_one_server()),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.detect",
            AsyncMock(return_value=[]),
        ),
    ):
        result = await explain_fleet_health(ctx)

    assert result.overall == "healthy"
    assert any("healthy" in r for r in result.reasons)


@pytest.mark.asyncio
async def test_offline_partial_outage_on_confirmed() -> None:
    """Offline + 1 confirmed signal → overall='partial_outage'."""
    prom = _empty_prom()
    llm = _make_offline_llm()
    ctx = ObservatoryContext(prom=prom, llm=llm).guard(needs=NEEDS)

    with (
        patch(
            "observatory_server.tools.explain_fleet_health.list_mcp_servers",
            AsyncMock(return_value=["svc-a"]),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.get_fleet_health",
            AsyncMock(return_value=_fleet_one_server()),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.detect",
            AsyncMock(return_value=[_signal("confirmed")]),
        ),
    ):
        result = await explain_fleet_health(ctx)

    assert result.overall == "partial_outage"


@pytest.mark.asyncio
async def test_offline_degraded_on_suspected() -> None:
    """Offline + 1 suspected signal (no confirmed) → overall='degraded'."""
    prom = _empty_prom()
    llm = _make_offline_llm()
    ctx = ObservatoryContext(prom=prom, llm=llm).guard(needs=NEEDS)

    with (
        patch(
            "observatory_server.tools.explain_fleet_health.list_mcp_servers",
            AsyncMock(return_value=["svc-a"]),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.get_fleet_health",
            AsyncMock(return_value=_fleet_one_server()),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.detect",
            AsyncMock(return_value=[_signal("suspected")]),
        ),
    ):
        result = await explain_fleet_health(ctx)

    assert result.overall == "degraded"


@pytest.mark.asyncio
async def test_offline_unknown_on_empty_fleet() -> None:
    """Offline + no servers → overall='unknown'."""
    prom = _empty_prom()
    llm = _make_offline_llm()
    ctx = ObservatoryContext(prom=prom, llm=llm).guard(needs=NEEDS)

    with (
        patch(
            "observatory_server.tools.explain_fleet_health.list_mcp_servers",
            AsyncMock(return_value=[]),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.get_fleet_health",
            AsyncMock(return_value=_fleet_empty()),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.detect",
            AsyncMock(return_value=[]),
        ),
    ):
        result = await explain_fleet_health(ctx)

    assert result.overall == "unknown"


@pytest.mark.asyncio
async def test_llm_success_parses_output() -> None:
    """Online LLM returns a structured output → result fields match."""
    llm_output = _ExplanationLLMOutput(
        overall="degraded",
        reasons=["error rate elevated on svc-a"],
        recommendations=["roll back svc-a", "check logs"],
    )
    prom = _empty_prom()
    llm = _make_online_llm(llm_output)
    ctx = ObservatoryContext(prom=prom, llm=llm).guard(needs=NEEDS)

    with (
        patch(
            "observatory_server.tools.explain_fleet_health.list_mcp_servers",
            AsyncMock(return_value=["svc-a"]),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.get_fleet_health",
            AsyncMock(return_value=_fleet_one_server()),
        ),
        patch(
            "observatory_server.tools.explain_fleet_health.detect",
            AsyncMock(return_value=[]),
        ),
    ):
        result = await explain_fleet_health(ctx)

    assert result.overall == "degraded"
    assert result.reasons == llm_output.reasons
    assert result.recommendations == llm_output.recommendations
