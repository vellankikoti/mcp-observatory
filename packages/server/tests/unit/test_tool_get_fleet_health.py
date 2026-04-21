from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from observatory_server.core.context import ObservatoryContext
from observatory_server.core.models import AbandonmentSignal, Capability
from observatory_server.tools.get_fleet_health import NEEDS, get_fleet_health


def _ctx(prom) -> ObservatoryContext:
    return ObservatoryContext(prom=prom, llm=MagicMock())


def test_needs_is_prom_only() -> None:
    assert frozenset({Capability.PROM}) == NEEDS


@pytest.mark.asyncio
async def test_fleet_health_with_two_services() -> None:
    """Two services, no abandonment signals — both appear in result."""
    prom = MagicMock()

    async def _query(promql: str):
        # list_mcp_servers query → returns 2 services
        if "count_over_time" in promql:
            return {
                "result": [
                    {"metric": {"service": "svc-a"}, "value": [0, "1"]},
                    {"metric": {"service": "svc-b"}, "value": [0, "1"]},
                ]
            }
        # abandonment baseline / current / error spike queries → empty
        if "avg_over_time" in promql or "rate(mcp_tool_calls_total" in promql:
            return {"result": []}
        # tool count queries per service
        if "count by (tool)" in promql:
            return {"result": [{"value": [0, "5"]}]}
        # error rate / p99 → empty
        return {"result": []}

    prom.query = _query
    ctx = _ctx(prom).guard(needs=NEEDS)
    result = await get_fleet_health(ctx, window="24h")

    assert len(result.servers) == 2
    service_names = {s.service for s in result.servers}
    assert service_names == {"svc-a", "svc-b"}
    for srv in result.servers:
        assert srv.total_tools == 5


@pytest.mark.asyncio
async def test_empty_fleet_returns_empty_servers() -> None:
    """list_mcp_servers returns [] → FleetHealth.servers is empty."""
    prom = MagicMock()

    async def _query(promql: str):
        return {"result": []}

    prom.query = _query
    ctx = _ctx(prom).guard(needs=NEEDS)
    result = await get_fleet_health(ctx)

    assert result.servers == []


@pytest.mark.asyncio
async def test_abandonment_signals_lower_healthy_count() -> None:
    """1 service + 1 confirmed signal + 10 tools → healthy_count == 9, abandoned_count == 1."""
    prom = MagicMock()

    async def _query(promql: str):
        if "count_over_time" in promql:
            return {"result": [{"metric": {"service": "svc-x"}, "value": [0, "1"]}]}
        if "count by (tool)" in promql:
            return {"result": [{"value": [0, "10"]}]}
        return {"result": []}

    prom.query = _query

    confirmed_signal = AbandonmentSignal(
        service="svc-x",
        tool="my_tool",
        status="confirmed",
        baseline_rate=1.0,
        current_rate=0.0,
        drop_pct=100.0,
    )

    ctx = _ctx(prom).guard(needs=NEEDS)

    with patch(
        "observatory_server.tools.get_fleet_health.detect",
        AsyncMock(return_value=[confirmed_signal]),
    ):
        result = await get_fleet_health(ctx)

    assert len(result.servers) == 1
    srv = result.servers[0]
    assert srv.total_tools == 10
    assert srv.abandoned_count == 1
    assert srv.healthy_count == 9
