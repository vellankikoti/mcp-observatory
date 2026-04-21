from __future__ import annotations

import asyncio
import sys

import typer

from observatory.adapters.llm import LLMAdapter, LLMConfig
from observatory.adapters.prom import PromAdapter, PromConfig
from observatory.core.context import ObservatoryContext
from observatory.reports.json import render_json
from observatory.reports.markdown import render_markdown
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

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="MCP Observatory — query tools for observing distributed MCP server fleets.",
)

_DEFAULT_PROM_URL = "http://localhost:9090"


def _render(model: object, fmt: str) -> str:
    if fmt == "json":
        return render_json(model)
    if fmt in ("md", "markdown"):
        return render_markdown(model)
    raise typer.BadParameter(f"unknown format: {fmt}")


def _build_ctx(
    prom_url: str | None,
    llm_provider: str | None = None,
) -> ObservatoryContext:
    prom = PromAdapter(PromConfig(base_url=prom_url or _DEFAULT_PROM_URL))
    llm = LLMAdapter(LLMConfig.from_sources(cli_provider=llm_provider))
    return ObservatoryContext(prom=prom, llm=llm)


@app.command("list-mcp-servers")
def list_mcp_servers_cmd(
    window: str = typer.Option("24h", "--window", "-w", help="Look-back window (e.g. 1h, 24h, 7d)"),
    prom_url: str | None = typer.Option(None, "--prom-url", help="Prometheus base URL"),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json or md"),
) -> None:
    """List unique MCP server service names seen in Prometheus over the given window."""

    async def _go() -> int:
        ctx = _build_ctx(prom_url).guard(needs=LIST_SERVERS_NEEDS)
        services = await _list_mcp_servers(ctx, window=window)
        sys.stdout.write(_render(services, fmt))
        return 0

    raise typer.Exit(asyncio.run(_go()))


@app.command("get-tool-call-rate")
def get_tool_call_rate_cmd(
    service: str = typer.Argument(..., help="MCP server service name"),
    tool: str | None = typer.Option(None, "--tool", "-t", help="Filter to a specific tool name"),
    window: str = typer.Option("1h", "--window", "-w", help="Look-back window (e.g. 30m, 1h, 6h)"),
    prom_url: str | None = typer.Option(None, "--prom-url", help="Prometheus base URL"),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json or md"),
) -> None:
    """Return call-rate TimeSeries for an MCP server (optionally filtered by tool)."""

    async def _go() -> int:
        ctx = _build_ctx(prom_url).guard(needs=GET_RATE_NEEDS)
        ts = await _get_tool_call_rate(ctx, service=service, tool=tool, window=window)
        sys.stdout.write(_render(ts, fmt))
        return 0

    raise typer.Exit(asyncio.run(_go()))


@app.command("get-tool-error-rate")
def get_tool_error_rate_cmd(
    service: str = typer.Argument(..., help="MCP server service name"),
    tool: str | None = typer.Option(None, "--tool", "-t", help="Filter to a specific tool name"),
    window: str = typer.Option("1h", "--window", "-w", help="Look-back window (e.g. 30m, 1h, 6h)"),
    prom_url: str | None = typer.Option(None, "--prom-url", help="Prometheus base URL"),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json or md"),
) -> None:
    """Return error-rate TimeSeries (ratio of error calls to total) for an MCP service."""

    async def _go() -> int:
        ctx = _build_ctx(prom_url).guard(needs=GET_ERROR_RATE_NEEDS)
        ts = await _get_tool_error_rate(ctx, service=service, tool=tool, window=window)
        sys.stdout.write(_render(ts, fmt))
        return 0

    raise typer.Exit(asyncio.run(_go()))


@app.command("get-tool-latency-p99")
def get_tool_latency_p99_cmd(
    service: str = typer.Argument(..., help="MCP server service name"),
    tool: str | None = typer.Option(None, "--tool", "-t", help="Filter to a specific tool name"),
    window: str = typer.Option("1h", "--window", "-w", help="Look-back window (e.g. 30m, 1h, 6h)"),
    prom_url: str | None = typer.Option(None, "--prom-url", help="Prometheus base URL"),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json or md"),
) -> None:
    """Return p99 latency TimeSeries (seconds) for an MCP service via histogram_quantile."""

    async def _go() -> int:
        ctx = _build_ctx(prom_url).guard(needs=GET_LATENCY_NEEDS)
        ts = await _get_tool_latency_p99(ctx, service=service, tool=tool, window=window)
        sys.stdout.write(_render(ts, fmt))
        return 0

    raise typer.Exit(asyncio.run(_go()))


@app.command("compare-servers")
def compare_servers_cmd(
    service_a: str = typer.Argument(..., help="First MCP server service name"),
    service_b: str = typer.Argument(..., help="Second MCP server service name"),
    window: str = typer.Option("1h", "--window", "-w", help="Look-back window (e.g. 30m, 1h, 6h)"),
    prom_url: str | None = typer.Option(None, "--prom-url", help="Prometheus base URL"),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json or md"),
) -> None:
    """Compare two MCP services by tool count, error rate, and p99 latency."""

    async def _go() -> int:
        ctx = _build_ctx(prom_url).guard(needs=COMPARE_NEEDS)
        comparison = await _compare_servers(
            ctx, service_a=service_a, service_b=service_b, window=window
        )
        sys.stdout.write(_render(comparison, fmt))
        return 0

    raise typer.Exit(asyncio.run(_go()))


@app.command("serve-mcp")
def serve_mcp() -> None:
    """Run the MCP stdio server."""
    from observatory.mcp_server import run_stdio

    run_stdio()


if __name__ == "__main__":
    app()
