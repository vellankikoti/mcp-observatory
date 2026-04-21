from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from observatory_server.core.context import ObservatoryContext
from observatory_server.tools.list_mcp_servers import NEEDS, list_mcp_servers


def _ctx(prom_result: dict) -> ObservatoryContext:
    prom = MagicMock()
    prom.query = AsyncMock(return_value=prom_result)
    return ObservatoryContext(prom=prom, llm=MagicMock())


@pytest.mark.asyncio
async def test_returns_unique_services_sorted():
    data = {
        "result": [
            {"metric": {"service": "b"}, "value": [0, "5"]},
            {"metric": {"service": "a"}, "value": [0, "3"]},
        ]
    }
    ctx = _ctx(data).guard(needs=NEEDS)
    services = await list_mcp_servers(ctx)
    assert services == ["a", "b"]


@pytest.mark.asyncio
async def test_empty_result_returns_empty_list():
    ctx = _ctx({"result": []}).guard(needs=NEEDS)
    assert await list_mcp_servers(ctx) == []


@pytest.mark.asyncio
async def test_duplicates_deduped():
    data = {
        "result": [
            {"metric": {"service": "x"}, "value": [0, "1"]},
            {"metric": {"service": "x"}, "value": [0, "2"]},
        ]
    }
    ctx = _ctx(data).guard(needs=NEEDS)
    assert await list_mcp_servers(ctx) == ["x"]
