# mcp-observatory

> Production-grade observability for distributed MCP server fleets.

**Status:** v0.1.0 — walking skeleton (two-package monorepo, query tools, SDK).

## Packages

| Package | PyPI name | Description |
|---------|-----------|-------------|
| `packages/server` | `mcp-observatory` | MCP query router — 2 query tools, Typer CLI, FastMCP surface |
| `packages/sdk` | `mcp-observatory-sdk` | Tiny SDK: `instrument(server)`, Prometheus metrics, OTel spans, ASGI `/metrics` |

## Quick install

```bash
pip install mcp-observatory mcp-observatory-sdk
```

## Development

```bash
uv venv
uv pip install -e "packages/sdk[dev]" -e "packages/server[dev]"
uv run pytest
```

## License

Apache 2.0
