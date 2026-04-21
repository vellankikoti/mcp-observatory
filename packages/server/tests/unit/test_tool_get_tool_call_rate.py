from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from observatory.core.context import ObservatoryContext
from observatory.tools.get_tool_call_rate import NEEDS, get_tool_call_rate


def _ctx(prom_result: dict) -> ObservatoryContext:
    prom = MagicMock()
    prom.query_range = AsyncMock(return_value=prom_result)
    return ObservatoryContext(prom=prom, llm=MagicMock())


@pytest.mark.asyncio
async def test_service_only_happy_path():
    now = time.time()
    data = {
        "result": [
            {
                "metric": {},
                "values": [
                    [now - 60, "1.5"],
                    [now, "2.0"],
                ],
            }
        ]
    }
    ctx = _ctx(data).guard(needs=NEEDS)
    ts = await get_tool_call_rate(ctx, service="my-service")
    assert len(ts.samples) == 2
    assert ts.promql == 'sum(rate(mcp_tool_calls_total{service="my-service"}[5m]))'


@pytest.mark.asyncio
async def test_service_and_tool_promql_contains_both_labels():
    data = {"result": [{"metric": {}, "values": [[time.time(), "3.0"]]}]}
    ctx = _ctx(data).guard(needs=NEEDS)
    ts = await get_tool_call_rate(ctx, service="svc", tool="my_tool")
    assert 'service="svc"' in ts.promql
    assert 'tool="my_tool"' in ts.promql


@pytest.mark.asyncio
async def test_invalid_window_raises_value_error():
    ctx = _ctx({"result": []}).guard(needs=NEEDS)
    with pytest.raises(ValueError, match="invalid window"):
        await get_tool_call_rate(ctx, service="svc", window="bad")
