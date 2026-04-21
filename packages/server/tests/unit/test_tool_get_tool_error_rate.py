from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from observatory_server.core.context import ObservatoryContext
from observatory_server.tools.get_tool_error_rate import NEEDS, get_tool_error_rate


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
                    [now - 60, "0.05"],
                    [now, "0.10"],
                ],
            }
        ]
    }
    ctx = _ctx(data).guard(needs=NEEDS)
    ts = await get_tool_error_rate(ctx, service="my-service")
    assert len(ts.samples) == 2
    assert 'outcome="error"' in ts.promql
    assert 'service="my-service"' in ts.promql


@pytest.mark.asyncio
async def test_tool_clause_included_when_tool_given() -> None:
    data = {"result": [{"metric": {}, "values": [[time.time(), "0.02"]]}]}
    ctx = _ctx(data).guard(needs=NEEDS)
    ts = await get_tool_error_rate(ctx, service="svc", tool="my_tool")
    assert 'tool="my_tool"' in ts.promql
    assert 'service="svc"' in ts.promql
    assert 'outcome="error"' in ts.promql


@pytest.mark.asyncio
async def test_invalid_window_raises_value_error() -> None:
    ctx = _ctx({"result": []}).guard(needs=NEEDS)
    with pytest.raises(ValueError, match="invalid window"):
        await get_tool_error_rate(ctx, service="svc", window="bad")
