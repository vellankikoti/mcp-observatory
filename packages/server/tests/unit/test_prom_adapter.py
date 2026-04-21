from __future__ import annotations

import json

import pytest
from observatory.adapters.prom import PromAdapter, PromConfig

try:
    from pytest_httpx import HTTPXMock
except ImportError:  # pragma: no cover
    pytest.skip("pytest-httpx not installed", allow_module_level=True)


PROM_BASE = "http://prometheus:9090"
PROMQL = "up"
FAKE_RESPONSE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [{"metric": {"job": "mcp-observatory"}, "value": [1700000000, "1"]}],
    },
}


@pytest.mark.asyncio
async def test_query_happy_path(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        content=json.dumps(FAKE_RESPONSE).encode(),
        headers={"Content-Type": "application/json"},
    )
    adapter = PromAdapter(PromConfig(base_url=PROM_BASE))
    result = await adapter.query(PROMQL)
    assert result["resultType"] == "vector"
    assert len(result["result"]) == 1
    await adapter.close()


@pytest.mark.asyncio
async def test_query_raises_when_no_base_url() -> None:
    adapter = PromAdapter(PromConfig(base_url=None))
    assert adapter.available is False
    with pytest.raises(RuntimeError, match="Prometheus base URL not configured"):
        await adapter.query(PROMQL)
