from __future__ import annotations

import asyncio

import pytest
from observatory_sdk.instrument import instrument
from observatory_sdk.metrics import new_registry
from prometheus_client import generate_latest


class FakeServer:
    def __init__(self) -> None:
        self.registered: dict[str, object] = {}

    def tool(self, *, name: str | None = None) -> object:  # type: ignore[override]
        def decorator(fn: object) -> object:
            tool_name = name or getattr(fn, "__name__", "unknown")
            self.registered[tool_name] = fn
            return fn

        return decorator


def test_instrument_wraps_and_counts_success() -> None:
    server = FakeServer()
    reg = new_registry()
    instrument(server, service_name="x", registry=reg)

    @server.tool(name="t")  # type: ignore[misc]
    async def t() -> str:
        return "ok"

    result = asyncio.run(server.registered["t"]())  # type: ignore[operator]
    assert result == "ok"

    body = generate_latest(reg).decode()
    assert 'mcp_tool_calls_total{outcome="success",service="x",tool="t"} 1.0' in body


def test_instrument_wraps_and_counts_error() -> None:
    server = FakeServer()
    reg = new_registry()
    instrument(server, service_name="svc", registry=reg)

    @server.tool(name="boom")  # type: ignore[misc]
    async def boom() -> str:
        raise ValueError("oops")

    with pytest.raises(ValueError, match="oops"):
        asyncio.run(server.registered["boom"]())  # type: ignore[operator]

    body = generate_latest(reg).decode()
    assert 'mcp_tool_calls_total{outcome="error",service="svc",tool="boom"} 1.0' in body


def test_instrument_tool_filter_skips() -> None:
    server = FakeServer()
    reg = new_registry()
    instrument(server, service_name="svc", tool_filter=lambda n: n != "skip_me", registry=reg)

    @server.tool(name="skip_me")  # type: ignore[misc]
    async def skip_me() -> str:
        return "skip"

    @server.tool(name="do_me")  # type: ignore[misc]
    async def do_me() -> str:
        return "do"

    # Call both
    asyncio.run(server.registered["skip_me"]())  # type: ignore[operator]
    asyncio.run(server.registered["do_me"]())  # type: ignore[operator]

    body = generate_latest(reg).decode()
    # skip_me should NOT be in metrics
    assert 'tool="skip_me"' not in body
    # do_me SHOULD be in metrics
    assert 'tool="do_me"' in body


def test_instrument_wraps_async_tool_preserving_return_value() -> None:
    server = FakeServer()
    reg = new_registry()
    instrument(server, service_name="svc", registry=reg)

    @server.tool(name="greet")  # type: ignore[misc]
    async def greet() -> dict[str, str]:
        return {"hello": "world"}

    result = asyncio.run(server.registered["greet"]())  # type: ignore[operator]
    assert result == {"hello": "world"}
