from __future__ import annotations

from fastmcp import FastMCP

from observatory.adapters.llm import LLMAdapter, LLMConfig
from observatory.adapters.prom import PromAdapter, PromConfig
from observatory.core.context import ObservatoryContext
from observatory.core.models import TimeSeries
from observatory.tools.get_tool_call_rate import NEEDS as GET_RATE_NEEDS
from observatory.tools.get_tool_call_rate import get_tool_call_rate as _get_tool_call_rate
from observatory.tools.list_mcp_servers import NEEDS as LIST_SERVERS_NEEDS
from observatory.tools.list_mcp_servers import list_mcp_servers as _list_mcp_servers

_DEFAULT_PROM_URL = "http://localhost:9090"


def _build_ctx() -> ObservatoryContext:
    prom = PromAdapter(PromConfig(base_url=_DEFAULT_PROM_URL))
    llm = LLMAdapter(LLMConfig.from_sources())
    return ObservatoryContext(prom=prom, llm=llm)


def build_server() -> FastMCP:
    server = FastMCP("mcp-observatory")

    @server.tool(name="list_mcp_servers")
    async def list_mcp_servers_tool(window: str = "24h") -> list[str]:
        """Return sorted unique MCP server service names seen in Prometheus over the given window."""
        ctx = _build_ctx().guard(needs=LIST_SERVERS_NEEDS)
        return await _list_mcp_servers(ctx, window=window)

    @server.tool(name="get_tool_call_rate")
    async def get_tool_call_rate_tool(
        service: str,
        tool: str | None = None,
        window: str = "1h",
    ) -> TimeSeries:
        """Return call-rate TimeSeries for an MCP server (optionally filtered by tool)."""
        ctx = _build_ctx().guard(needs=GET_RATE_NEEDS)
        return await _get_tool_call_rate(ctx, service=service, tool=tool, window=window)

    return server


def run_stdio() -> None:
    build_server().run()
