from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest


async def _readline_timeout(reader: asyncio.StreamReader, deadline_s: float = 15.0) -> bytes:
    async with asyncio.timeout(deadline_s):
        return await reader.readline()


@pytest.mark.mcp_contract
@pytest.mark.asyncio
async def test_mcp_tools_list_over_stdio() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "observatory.cli", "serve-mcp",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "OBSERVATORY_OFFLINE": "1"},
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        proc.stdin.write((json.dumps(init) + "\n").encode())
        await proc.stdin.drain()
        _ = await _readline_timeout(proc.stdout)
        initialized = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        proc.stdin.write((json.dumps(initialized) + "\n").encode())
        await proc.stdin.drain()
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        proc.stdin.write((json.dumps(list_req) + "\n").encode())
        await proc.stdin.drain()
        tools_resp = None
        for _ in range(10):
            raw = await _readline_timeout(proc.stdout)
            if not raw:
                break
            try:
                r = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if r.get("id") == 2 and "result" in r:
                tools_resp = r
                break
        assert tools_resp is not None
        names = {t["name"] for t in tools_resp["result"]["tools"]}
        assert {"list_mcp_servers", "get_tool_call_rate"}.issubset(names)
    finally:
        proc.terminate()
        await proc.wait()
