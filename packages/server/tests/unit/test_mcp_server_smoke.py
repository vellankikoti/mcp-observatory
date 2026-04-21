from __future__ import annotations

import asyncio

from observatory.mcp_server import build_server


def test_mcp_server_exposes_expected_tools() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert "list_mcp_servers" in names
    assert "get_tool_call_rate" in names
