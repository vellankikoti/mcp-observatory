from __future__ import annotations

import httpx
import pytest
from observatory_sdk.asgi import metrics_asgi_app
from observatory_sdk.metrics import ToolCallOutcome, new_registry, record_tool_call


@pytest.mark.asyncio
async def test_asgi_metrics_app_returns_prom_format() -> None:
    reg = new_registry()
    record_tool_call(reg, "svc", "tool1", 0.1, ToolCallOutcome.SUCCESS)

    app = metrics_asgi_app(reg)
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/metrics")

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "mcp_tool_calls_total" in body
