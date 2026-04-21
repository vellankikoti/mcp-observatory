from __future__ import annotations

from fastmcp import FastMCP

from observatory.adapters.llm import LLMAdapter, LLMConfig
from observatory.adapters.prom import PromAdapter, PromConfig
from observatory.core.context import ObservatoryContext
from observatory.core.models import ServerComparison, TimeSeries
from observatory.tools.compare_servers import NEEDS as COMPARE_NEEDS
from observatory.tools.compare_servers import compare_servers as _compare_servers
from observatory.tools.get_tool_call_rate import NEEDS as GET_RATE_NEEDS
from observatory.tools.get_tool_call_rate import get_tool_call_rate as _get_tool_call_rate
from observatory.tools.get_tool_error_rate import NEEDS as GET_ERROR_RATE_NEEDS
from observatory.tools.get_tool_error_rate import get_tool_error_rate as _get_tool_error_rate
from observatory.tools.get_tool_latency_p99 import NEEDS as GET_LATENCY_NEEDS
from observatory.tools.get_tool_latency_p99 import get_tool_latency_p99 as _get_tool_latency_p99
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

    @server.tool(name="get_tool_error_rate")
    async def get_tool_error_rate_tool(
        service: str,
        tool: str | None = None,
        window: str = "1h",
    ) -> TimeSeries:
        """Return error-rate TimeSeries (ratio of error calls to total) for an MCP service."""
        ctx = _build_ctx().guard(needs=GET_ERROR_RATE_NEEDS)
        return await _get_tool_error_rate(ctx, service=service, tool=tool, window=window)

    @server.tool(name="get_tool_latency_p99")
    async def get_tool_latency_p99_tool(
        service: str,
        tool: str | None = None,
        window: str = "1h",
    ) -> TimeSeries:
        """Return p99 latency TimeSeries (seconds) for an MCP service via histogram_quantile."""
        ctx = _build_ctx().guard(needs=GET_LATENCY_NEEDS)
        return await _get_tool_latency_p99(ctx, service=service, tool=tool, window=window)

    @server.tool(name="compare_servers")
    async def compare_servers_tool(
        service_a: str,
        service_b: str,
        window: str = "1h",
    ) -> ServerComparison:
        """Compare two MCP services by tool count, error rate, and p99 latency."""
        ctx = _build_ctx().guard(needs=COMPARE_NEEDS)
        return await _compare_servers(ctx, service_a=service_a, service_b=service_b, window=window)

    return server


def run_stdio() -> None:
    build_server().run()
