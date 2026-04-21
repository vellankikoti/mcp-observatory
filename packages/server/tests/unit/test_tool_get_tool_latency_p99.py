from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from observatory.core.context import ObservatoryContext
from observatory.tools.get_tool_latency_p99 import NEEDS, get_tool_latency_p99


def _ctx(prom_result: dict) -> ObservatoryContext:
    prom = MagicMock()
    prom.query_range = AsyncMock(return_value=prom_result)
    return ObservatoryContext(prom=prom, llm=MagicMock())


@pytest.mark.asyncio
async def test_service_only_returns_timeseries() -> None:
    now = time.time()
    data = {
        "result": [
            {
                "metric": {},
                "values": [
                    [now - 60, "0.250"],
                    [now, "0.300"],
                ],
            }
        ]
    }
    ctx = _ctx(data).guard(needs=NEEDS)
    ts = await get_tool_latency_p99(ctx, service="my-service")
    assert len(ts.samples) == 2
    assert "histogram_quantile(0.99" in ts.promql
    assert 'service="my-service"' in ts.promql


@pytest.mark.asyncio
async def test_tool_clause_included_when_tool_given() -> None:
    data = {"result": [{"metric": {}, "values": [[time.time(), "0.150"]]}]}
    ctx = _ctx(data).guard(needs=NEEDS)
    ts = await get_tool_latency_p99(ctx, service="svc", tool="my_tool")
    assert 'tool="my_tool"' in ts.promql
    assert 'service="svc"' in ts.promql
    assert "histogram_quantile" in ts.promql


@pytest.mark.asyncio
async def test_invalid_window_raises_value_error() -> None:
    ctx = _ctx({"result": []}).guard(needs=NEEDS)
    with pytest.raises(ValueError, match="invalid window"):
        await get_tool_latency_p99(ctx, service="svc", window="bad")
