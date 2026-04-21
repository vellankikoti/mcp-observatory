# mcp-observatory-sdk

Tiny SDK that instruments MCP servers with Prometheus metrics + OpenTelemetry spans.

One-line adoption in a FastMCP server:

```python
from fastmcp import FastMCP
from observatory_sdk import instrument

server = FastMCP("my-server")
instrument(server, service_name="my-server", prometheus_port=9090)
# ... register tools as usual ...
```

Zero runtime deps beyond `prometheus-client` and `opentelemetry-api`.

Companion project: [**mcp-observatory**](https://github.com/vellankikoti/mcp-observatory) — the query-router MCP server that consumes the metrics this SDK emits.
