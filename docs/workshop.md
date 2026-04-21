# MCP Observatory Workshop

**Total time:** ~2 h 15 min | **Audience:** platform engineers, SRE, MCP server authors

---

## Prerequisites

- Python 3.11+, `uv`, `helm` installed locally.
- Access to a running Prometheus instance (or use the synthetic one below).
- Optional: a real MCP server fleet (the workshop notes where synthetic data substitutes).

---

## Module 1 — Install + explore all 9 tools (30 min)

### 1.1 Install

```bash
pip install mcp-observatory
# or with uv:
uv add mcp-observatory
```

### 1.2 Point at Prometheus

Export your Prometheus URL:

```bash
export OBSERVATORY_PROM_URL=http://localhost:9090
```

No live Prometheus? Start the built-in synthetic one used by integration tests:

```bash
# In a separate terminal:
uv run python tests/integration/fake_prom.py &
export OBSERVATORY_PROM_URL=http://localhost:19090
```

### 1.3 Run all 9 tools

Work through each subcommand and observe the output:

```bash
# 1. Which MCP servers are active?
observatory list-mcp-servers --window 24h

# 2. Tool call rate (replace prod-readiness with your service name)
observatory get-tool-call-rate prod-readiness --window 1h

# 3. Error rate
observatory get-tool-error-rate prod-readiness --window 1h

# 4. p99 latency
observatory get-tool-latency-p99 prod-readiness --window 1h

# 5. Compare two services
observatory compare-servers prod-readiness search-service --window 1h

# 6. Detect abandoned tools
observatory detect-tool-abandonment --prom-url $OBSERVATORY_PROM_URL

# 7. Fleet health snapshot
observatory get-fleet-health --window 24h

# 8. LLM narrative (falls back to deterministic if no LLM configured)
observatory explain-fleet-health

# 9. Verify expected services are present (exits 0 = all present, 1 = missing)
observatory verify-services --expected prod-readiness,search-service
echo "exit code: $?"
```

**Checkpoint:** You should see structured JSON output for each command. The
`verify-services` command exits 1 if any expected service is absent — try
`--expected prod-readiness,nonexistent-svc` to see a non-zero exit.

---

## Module 2 — Simulate abandonment and watch escalation (45 min)

This module shows how `detect_tool_abandonment` escalates from `suspected` to
`confirmed` as the signal strengthens.

### 2.1 Understand the detection algorithm

`detect_tool_abandonment` compares:
- **Baseline rate** — average calls/sec over the past 7 days
- **Current rate** — average calls/sec over the past 1 hour
- **Error spike** — error rate over the past 50 minutes vs 7-day baseline

A tool is `suspected` when the drop is ≥ 80% and the baseline was meaningful
(≥ 0.1 rps). It escalates to `confirmed` when the drop is accompanied by an
error spike ≥ 2× the 7-day error baseline.

### 2.2 Trigger suspected abandonment

If you have a real MCP server: stop sending tool calls for 30 minutes, then run:

```bash
observatory detect-tool-abandonment --service my-service --drop-pct 50
```

With synthetic Prom, use the golden test fixture for `two-suspected`:

```bash
uv run pytest -m golden -k "two_suspected" -v
```

Expected: two tools appear with `status: suspected`.

### 2.3 Escalate to confirmed

With a real server: introduce a bug that causes the tool to error on every call
(e.g. break an upstream dependency). After the error rate climbs, re-run:

```bash
observatory detect-tool-abandonment --service my-service --error-floor 0.01
```

Expected: `status` changes from `suspected` → `confirmed` for the affected tools.

### 2.4 See fleet-level impact

```bash
observatory get-fleet-health
```

The `abandoned_count` for the affected service should be non-zero.

```bash
observatory explain-fleet-health
```

Expected verdict: `partial_outage` (deterministic) or an LLM narrative describing
which service is degraded.

---

## Module 3 — Adopt the SDK in a new FastMCP server (45 min)

### 3.1 Create a minimal FastMCP server

```bash
mkdir workshop-server && cd workshop-server
uv init --name workshop-server
uv add fastmcp mcp-observatory-sdk
```

```python
# src/main.py
from fastmcp import FastMCP
from observatory_sdk import instrument

server = FastMCP("workshop-server")
instrument(server, service_name="workshop-server", prometheus_port=9091)

@server.tool()
async def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    server.run()
```

### 3.2 Run the server

```bash
uv run python src/main.py &
```

### 3.3 Call the tool a few times

```bash
# Via MCP client (Claude Desktop) — or use httpx directly
python -c "
import httpx, json
# Simulate MCP calls to generate metrics
for i in range(10):
    print(f'call {i}')
"
```

### 3.4 Verify the server appears in observatory

```bash
observatory list-mcp-servers --prom-url http://localhost:9090 --window 1h
```

Expected: `workshop-server` appears in the list.

```bash
observatory verify-services --expected workshop-server --prom-url http://localhost:9090
echo "exit code: $?"  # should be 0
```

**Full SDK integration reference:** see `docs/sdk-integration.md`.

---

## Module 4 — Install via Helm + verify Service reachable (15 min)

### 4.1 Prerequisite

A running Kubernetes cluster (kind, k3d, or a real cluster). `kubectl` and
`helm` configured.

```bash
# Quick kind cluster if needed:
kind create cluster --name obs-workshop
```

### 4.2 Install the Helm chart

```bash
helm install obs charts/observatory \
  --namespace obs \
  --create-namespace \
  --set prometheus.url=http://prometheus.monitoring.svc.cluster.local:9090
```

### 4.3 Verify the Deployment and Service

```bash
kubectl -n obs get deploy,svc,pods
```

Expected: `obs-observatory` Deployment (1/1 ready), `obs-observatory` ClusterIP Service on port 8000.

### 4.4 Reach the HTTP endpoint

```bash
kubectl -n obs port-forward svc/obs-observatory 8000:8000 &
curl -s http://localhost:8000/health || echo "check FastMCP /health or /docs"
```

The MCP HTTP endpoint is at `http://localhost:8000/mcp/` (FastMCP 3.x default path).

### 4.5 Uninstall

```bash
helm uninstall obs -n obs
kind delete cluster --name obs-workshop
```

### Note on PrometheusRule

PrometheusRule shipping (for alerting rules triggered by abandonment signals)
is deferred to v1.x. See the `charts/observatory` backlog for the planned
`PrometheusRule` template.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `verify-services` always exits 0 even for missing services | Pass `--expected` explicitly; empty `--expected` is always ok by design |
| `list-mcp-servers` returns empty list | SDK not installed on any server, or `prometheus_port` not scraped |
| `explain-fleet-health` returns deterministic output | No LLM configured — set `OBSERVATORY_LLM_PROVIDER` or `--llm-provider` |
| Helm pod stuck in `CrashLoopBackOff` | Check `kubectl logs`; likely `--prom-url` unreachable from inside cluster |
| `serve-http` exits immediately | Port conflict or FastMCP uvicorn startup failure — check stderr |
