# mcp-observatory

> Production-grade observability for distributed MCP server fleets.

**Status:** v1.0.0 — production-ready. 9 tools live. HTTP transport. Helm Deployment + Service.

[![PyPI](https://img.shields.io/pypi/v/mcp-observatory-server)](https://pypi.org/project/mcp-observatory-server/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Packages

| Package | PyPI name | Description |
|---------|-----------|-------------|
| `packages/server` | `mcp-observatory-server` | MCP query router — 9 tools, Typer CLI, FastMCP stdio + HTTP surfaces |
| `packages/sdk` | `mcp-observatory-sdk` | Tiny SDK: `instrument(server)`, Prometheus metrics, OTel spans, ASGI `/metrics` |

---

## 9 Tools

| Tool | CLI subcommand | Description |
|------|---------------|-------------|
| `list_mcp_servers` | `list-mcp-servers` | Unique MCP server service names seen in Prom over a window |
| `get_tool_call_rate` | `get-tool-call-rate` | Call-rate TimeSeries for a service (optionally filtered by tool) |
| `get_tool_error_rate` | `get-tool-error-rate` | Error-rate TimeSeries (ratio errors/total) |
| `get_tool_latency_p99` | `get-tool-latency-p99` | p99 latency TimeSeries via `histogram_quantile` |
| `compare_servers` | `compare-servers` | Side-by-side comparison of two services |
| `detect_tool_abandonment` | `detect-tool-abandonment` | Detect silently abandoned tools — `suspected` / `confirmed` |
| `get_fleet_health` | `get-fleet-health` | Fleet-wide health snapshot with per-server healthy/degraded/abandoned counts |
| `explain_fleet_health` | `explain-fleet-health` | LLM-driven narrative with deterministic fallback |
| `verify_services` | `verify-services` | Check expected services are present — exits 1 if any missing (CI gate) |

---

## Install

### A. pip

```bash
pip install mcp-observatory-server mcp-observatory-sdk
```

### B. uv

```bash
uv add mcp-observatory-server mcp-observatory-sdk
```

### C. uvx (no install)

```bash
uvx mcp-observatory-server list-mcp-servers --prom-url http://localhost:9090
```

### D. Docker

```bash
docker pull ghcr.io/vellankikoti/mcp-observatory-server:v1.0.0
docker run --rm ghcr.io/vellankikoti/mcp-observatory-server:v1.0.0 list-mcp-servers --help
```

### E. Helm (in-cluster HTTP transport)

```bash
helm repo add observatory https://vellankikoti.github.io/mcp-observatory
helm install obs observatory/observatory-server \
  --namespace obs \
  --create-namespace \
  --set prometheus.url=http://prometheus.monitoring.svc.cluster.local:9090
```

The chart deploys a `Deployment` running `observatory-server serve-http --port 8000`
and a `ClusterIP` Service. Access from within the cluster:
`http://obs-observatory.obs.svc.cluster.local:8000/mcp/`

---

## Quickstart — CLI

```bash
export OBSERVATORY_SERVER_PROM_URL=http://localhost:9090

# List active MCP servers
observatory-server list-mcp-servers --window 24h

# Tool call rate (1h window)
observatory-server get-tool-call-rate my-service --window 1h

# Error rate
observatory-server get-tool-error-rate my-service --window 1h

# p99 latency filtered to one tool
observatory-server get-tool-latency-p99 my-service --tool my_tool --window 1h

# Compare two services
observatory-server compare-servers svc-a svc-b --window 1h

# Detect silently abandoned tools
observatory-server detect-tool-abandonment

# Fleet-wide health snapshot
observatory-server get-fleet-health --window 24h

# LLM narrative (deterministic fallback when no LLM configured)
observatory-server explain-fleet-health

# CI gate — exits 1 if prod-readiness or search-service are absent
observatory-server verify-services --expected prod-readiness,search-service && echo "all present"

# Run as MCP stdio server (Claude Desktop / any MCP client)
observatory-server serve-mcp

# Run as MCP HTTP server (in-cluster, port 8000)
observatory-server serve-http --port 8000 --prom-url http://prometheus:9090 --no-llm
```

### MCP client config (Claude Desktop)

```json
{
  "mcpServers": {
    "observatory": {
      "command": "observatory-server",
      "args": ["serve-mcp"],
      "env": {
        "OBSERVATORY_SERVER_PROM_URL": "http://localhost:9090"
      }
    }
  }
}
```

---

## SDK integration

Instrument any [FastMCP](https://github.com/jlowin/fastmcp) server with two lines:

```python
from fastmcp import FastMCP
from observatory_sdk import instrument

server = FastMCP("my-service")
instrument(server, service_name="my-service", prometheus_port=9090)  # ← add this

@server.tool()
async def my_tool(query: str) -> str: ...
```

This exposes `mcp_tool_calls_total`, `mcp_tool_duration_seconds`, and
`mcp_tool_inflight` metrics plus OTel spans — the exact names `mcp-observatory-server`
queries.

Full guide: **[docs/sdk-integration.md](docs/sdk-integration.md)**

---

## LLM config

`explain-fleet-health` uses an LLM for narrative synthesis with full deterministic fallback.

```bash
# Ollama (local)
export OBSERVATORY_SERVER_LLM_PROVIDER=ollama/qwen2.5:7b

# Any LiteLLM-compatible provider
export OBSERVATORY_SERVER_LLM_PROVIDER=openai/gpt-4o-mini
export OPENAI_API_KEY=sk-...

# Disable LLM entirely
observatory-server explain-fleet-health  # falls back automatically when no provider set
```

---

## Verify image signature (cosign)

```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/vellankikoti/mcp-observatory" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/vellankikoti/mcp-observatory-server:v1.0.0
```

SBOM (CycloneDX) is attached as an OCI referrer — fetch with:

```bash
cosign download sbom ghcr.io/vellankikoti/mcp-observatory-server:v1.0.0
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `list-mcp-servers` returns empty | SDK not installed on any server, or Prom doesn't scrape the metrics port |
| `verify-services` always exits 0 | Empty `--expected` is always ok by design; pass explicit names |
| `explain-fleet-health` returns deterministic output | Set `OBSERVATORY_LLM_PROVIDER` or `--llm-provider` |
| Helm pod in CrashLoopBackOff | Check `kubectl logs`; `--prom-url` likely unreachable from inside cluster |
| `serve-http` exits immediately | Port conflict or uvicorn startup error — check stderr |
| mypy errors on `Optional` | Ensure Python 3.11+ is active (`uv python install 3.11`) |

---

## Development

```bash
uv venv
uv pip install -e "packages/sdk[dev]" -e "packages/server[dev]"

# Run all tests (≥75)
uv run pytest packages/server/tests packages/sdk/tests tests/ -q

# Golden tests (≥5) — no cluster needed
uv run pytest -m golden -v

# Integration — spins up synthetic Prom (1)
uv run pytest -m integration -v

# MCP stdio contract (1)
uv run pytest -m mcp_contract -v

# Helm tests (2)
uv run pytest tests/helm/ -v

# Linting + formatting
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/server/src packages/sdk/src
```

---

## License

Apache 2.0
