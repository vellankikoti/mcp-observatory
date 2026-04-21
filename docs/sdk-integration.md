# SDK Integration Guide — adopting `mcp-observatory-sdk` in a FastMCP server

This guide shows how any FastMCP server can adopt `mcp-observatory-sdk` to expose
the Prometheus metrics and OpenTelemetry spans that `mcp-observatory` needs.

---

## Why consistent metric names matter

`mcp-observatory` queries Prometheus for metrics named:

| Metric | Description |
|--------|-------------|
| `mcp_tool_calls_total` | Counter — `service`, `tool`, `outcome` labels |
| `mcp_tool_duration_seconds` | Histogram — `service`, `tool` labels |
| `mcp_tool_inflight` | Gauge — `service`, `tool` labels |

The **abandonment detection** algorithm (`detect_tool_abandonment`) compares a
7-day baseline rate against a 1-hour current rate.  If your server uses
non-standard metric names the baseline will always be zero and every tool will
appear healthy regardless of its actual state.

`instrument()` wraps every `@server.tool` handler at registration time and emits
exactly these metric names, so observatory sees all servers uniformly.

---

## Step 1 — install the SDK

```bash
pip install mcp-observatory-sdk
```

Or add it to your project's dependencies:

```toml
# pyproject.toml
dependencies = [
  "mcp-observatory-sdk>=1.0",
  ...
]
```

---

## Step 2 — call `instrument()` after creating your server

```python
from fastmcp import FastMCP
from observatory_sdk import instrument

server = FastMCP("my-service")

# IMPORTANT: call instrument() BEFORE @server.tool registrations
instrument(server, service_name="my-service", prometheus_port=9090)

@server.tool()
async def my_tool(query: str) -> str:
    ...
```

That is the entire integration.  `instrument()` monkey-patches the FastMCP tool
registration hook; any tool added **after** `instrument()` is automatically
wrapped.

---

## Worked example — prod-readiness server

Below is the minimal diff required to instrument the
[mcp-prod-readiness](https://github.com/vellankikoti/mcp-prod-readiness) server:

```diff
 from fastmcp import FastMCP
+from observatory_sdk import instrument

 def build_server() -> FastMCP:
     server = FastMCP("prod-readiness")
+    instrument(server, service_name="prod-readiness", prometheus_port=9090)

     @server.tool()
     async def check_deployment_health(namespace: str) -> dict:
         ...
```

Two lines added — that is all.

---

## What you get

After instrumentation the following are available:

### Prometheus metrics (port 9090 by default)

```
# HELP mcp_tool_calls_total Total number of MCP tool calls
# TYPE mcp_tool_calls_total counter
mcp_tool_calls_total{service="prod-readiness",tool="check_deployment_health",outcome="success"} 42

# HELP mcp_tool_duration_seconds MCP tool call duration in seconds
# TYPE mcp_tool_duration_seconds histogram
mcp_tool_duration_seconds_bucket{service="prod-readiness",tool="check_deployment_health",le="0.1"} 38

# HELP mcp_tool_inflight In-flight MCP tool calls
# TYPE mcp_tool_inflight gauge
mcp_tool_inflight{service="prod-readiness",tool="check_deployment_health"} 0
```

### OpenTelemetry spans

Each tool call emits a span named `tool.<tool_name>` with attributes:

- `tool.service` — the service name passed to `instrument()`
- `tool.name` — the registered tool name
- `tool.outcome` — `"success"` or `"error"`
- `tool.duration_s` — call duration in seconds

Configure your OTel exporter via the standard `OTEL_EXPORTER_OTLP_ENDPOINT`
environment variable.

---

## Scrape configuration

### Option A — prometheus-operator ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: prod-readiness
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: prod-readiness
  endpoints:
    - port: metrics
      path: /metrics
      interval: 15s
```

Expose the metrics port in your Service:

```yaml
ports:
  - name: metrics
    port: 9090
    targetPort: 9090
```

### Option B — scrape_config in prometheus.yml

```yaml
scrape_configs:
  - job_name: prod-readiness
    static_configs:
      - targets: ["prod-readiness.default.svc.cluster.local:9090"]
```

---

## Troubleshooting

### "All tools appear abandoned immediately after deploy"

**Cause:** `instrument()` was called *after* `@server.tool` registrations.

**Fix:** Move `instrument(server, ...)` to immediately after `FastMCP(...)` and
before any `@server.tool` decorators.

```python
# WRONG
server = FastMCP("my-service")

@server.tool()           # registered BEFORE instrument — not wrapped
async def my_tool(): ...

instrument(server, service_name="my-service")   # too late

# CORRECT
server = FastMCP("my-service")
instrument(server, service_name="my-service")   # wraps all subsequent tools

@server.tool()           # now wrapped
async def my_tool(): ...
```

### "Cardinality explosion in Prometheus"

**Cause:** passing a high-cardinality value (e.g. a user ID or request ID) as
the `service_name`.

**Fix:** `service_name` should be a static identifier for your server process,
e.g. `"prod-readiness"` or `"my-org/tools/search"`.  Never include per-request
values.

### "Metrics endpoint returns 404"

The SDK starts a lightweight HTTP server on `prometheus_port` (default: 9090)
serving `/metrics`.  Ensure:

1. The port is not blocked by a firewall rule or security group.
2. You are not running multiple servers on the same host with the same port —
   use `prometheus_port=0` to get a random free port, or assign distinct ports
   per process.

### "No spans in my tracing backend"

`instrument()` uses the OpenTelemetry API.  You must install and configure an SDK
implementation at startup:

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp
```

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry import trace

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
```

Without an SDK provider the API calls are no-ops — no error, no spans.
