# mcp-observatory

> Production-grade observability for distributed MCP server fleets.

**Status:** v0.4.0 — 8 tools live. Latest additions: `get_fleet_health` (fleet-wide health aggregation with per-server healthy/degraded/abandoned counts) and `explain_fleet_health` (LLM-driven narrative with deterministic fallback).

## Packages

| Package | PyPI name | Description |
|---------|-----------|-------------|
| `packages/server` | `mcp-observatory` | MCP query router — 8 query tools, Typer CLI, FastMCP stdio surface |
| `packages/sdk` | `mcp-observatory-sdk` | Tiny SDK: `instrument(server)`, Prometheus metrics, OTel spans, ASGI `/metrics` |

## Install

```bash
pip install mcp-observatory mcp-observatory-sdk
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add mcp-observatory mcp-observatory-sdk
```

## Quickstart — server

```bash
# List MCP servers seen in Prometheus over last 24h
observatory list-mcp-servers --prom-url http://localhost:9090

# Get per-tool call rate for a specific service (1h window)
observatory get-tool-call-rate my-service --window 1h --prom-url http://localhost:9090

# Get error rate for a service (ratio of error calls to total)
observatory get-tool-error-rate my-service --window 1h --prom-url http://localhost:9090

# Get p99 latency for a specific tool on a service
observatory get-tool-latency-p99 my-service --tool my_tool --window 1h --prom-url http://localhost:9090

# Compare two services side-by-side
observatory compare-servers svc-a svc-b --window 1h --prom-url http://localhost:9090

# Detect silently abandoned tools (hero feature — v0.3.0)
observatory detect-tool-abandonment --prom-url http://localhost:9090
observatory detect-tool-abandonment --service my-service --drop-pct 70 --prom-url http://localhost:9090

# Run as MCP stdio server (for Claude Desktop / any MCP client)
observatory serve-mcp
```

### MCP client config (Claude Desktop)

```json
{
  "mcpServers": {
    "observatory": {
      "command": "observatory",
      "args": ["serve-mcp"],
      "env": {
        "OBSERVATORY_PROM_URL": "http://localhost:9090"
      }
    }
  }
}
```

## Quickstart — SDK

Instrument any [FastMCP](https://github.com/jlowin/fastmcp) server with one line:

```python
from mcp_observatory_sdk import instrument

from myfastmcp_app import mcp   # your FastMCP instance

instrument(mcp, service_name="my-service")
```

This registers Prometheus counters and OTel spans for every tool call.

### Expose `/metrics` in your ASGI app

```python
from mcp_observatory_sdk import metrics_asgi_app

# Mount alongside your existing app
app.mount("/metrics", metrics_asgi_app())
```

### Low-level API

```python
from mcp_observatory_sdk import record_tool_call, ToolCallOutcome

record_tool_call(
    service="my-service",
    tool="my_tool",
    outcome=ToolCallOutcome.SUCCESS,
    duration_s=0.123,
)
```

## Development

```bash
uv venv
uv pip install -e "packages/sdk[dev]" -e "packages/server[dev]"

# Unit tests (60 total)
uv run pytest packages/server/tests packages/sdk/tests -q

# Golden tests — no cluster needed (3)
uv run pytest -m golden -v

# Integration — spins up synthetic Prom (1)
uv run pytest -m integration -v

# MCP stdio contract (1)
uv run pytest -m mcp_contract -v
```

## Docker

```bash
docker pull ghcr.io/vellankikoti/mcp-observatory:v0.3.0
docker run --rm ghcr.io/vellankikoti/mcp-observatory:v0.3.0 list-mcp-servers --help
```

## Helm

```bash
helm repo add observatory https://vellankikoti.github.io/mcp-observatory
helm install observatory observatory/observatory --set prometheus.url=http://prometheus:9090
```

Note: v0.1.0 chart ships RBAC only. A persistent Deployment is added in Plan 6 (HTTP transport).

## License

Apache 2.0
