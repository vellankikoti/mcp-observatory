from __future__ import annotations

import asyncio

from observatory_server.mcp_server import build_server


def test_mcp_server_exposes_expected_tools() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert "list_mcp_servers" in names
    assert "get_tool_call_rate" in names
    assert "get_tool_error_rate" in names
    assert "get_tool_latency_p99" in names
    assert "compare_servers" in names
    assert "detect_tool_abandonment" in names
    assert "get_fleet_health" in names
    assert "explain_fleet_health" in names
    assert "verify_services" in names
    assert len(names) >= 9
