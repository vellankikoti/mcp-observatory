# mcp-observatory — Design Spec

- **Date:** 2026-04-21
- **Project:** 02-mcp-observatory (third of four conference MCP projects)
- **Sibling projects:** `mcp-prod-readiness` v1.0.1, `mcp-deploy-intel` v1.0.0 — same stack, same release pipeline. Both will adopt this project's SDK in Plan 5.
- **Status:** Approved for implementation planning

## 1. Purpose & Vision

Give platform teams and MCP server operators **typed query primitives and a detection rule for spotting silent tool abandonment** in an MCP fleet — when AI agents stop using a degraded MCP tool and start hallucinating answers instead. Ship as two PyPI packages: a lightweight SDK any MCP server imports to emit standard Prom metrics + OTel spans, and a query-router MCP server that turns those metrics into typed tool calls (and a hero `detect_tool_abandonment` signal).

The core value is the **data plane + detection**: 8 query tools over any Prom-scraped fleet, plus a pure-PromQL detector that fires `suspected` on a frequency drop and `confirmed` when the drop correlates with a recent error spike. No LLM required for the hero feature.

**Non-goals for v1:**
- Writing to MCP servers / mutating anything.
- Ingesting metrics directly (Prom is the source of truth).
- Multi-tenant dashboards (one Prom = one fleet view).

## 2. Delivery Goals

- **Two PyPI packages** co-versioned from one monorepo: `mcp-observatory` (server+CLI) and `mcp-observatory-sdk` (the instrumentation SDK).
- Helm chart for in-cluster deployment of the server only.
- GitHub Action for PR checks (CLI-based).
- Cosign-signed image + CycloneDX SBOM on every release.
- Phased SemVer: `v0.1.0 → v1.0.0` across 6 plans.

## 3. Technical Stack

- Python 3.11+, async-first.
- Server: FastMCP 3.x, Typer, litellm, instructor, `httpx`, `opentelemetry-api`.
- SDK: `prometheus_client>=0.20`, `opentelemetry-api>=1.25` — **that is all**. No FastMCP, no Pydantic, no HTTP libs.
- Testing: `pytest` + `pytest-asyncio`. **No kind dependency** for the release gate — golden tests use recorded Prom responses.
- Release: PyPI trusted publisher, GHCR multi-arch, cosign keyless, CycloneDX SBOM.

## 4. Architecture

### 4.1 Repo layout

```
mcp-observatory/
├─ pyproject.toml            # workspace root (dev deps, ruff/mypy config)
├─ packages/
│  ├─ server/
│  │  ├─ pyproject.toml      # [project] name = "mcp-observatory"
│  │  ├─ src/observatory/
│  │  │  ├─ adapters/        # prom.py, llm.py (lifted from deploy-intel)
│  │  │  ├─ core/            # context, models, tracing
│  │  │  ├─ tools/           # 8 tool modules
│  │  │  ├─ rules/           # abandonment.py (detection)
│  │  │  ├─ cli.py
│  │  │  └─ mcp_server.py
│  │  └─ tests/unit/
│  └─ sdk/
│     ├─ pyproject.toml      # [project] name = "mcp-observatory-sdk"
│     ├─ src/observatory_sdk/
│     │  ├─ __init__.py      # public exports
│     │  ├─ instrument.py    # FastMCP wrapper
│     │  ├─ metrics.py       # Prom registry + counters/histogram/gauge
│     │  └─ tracing.py       # OTel span helpers
│     └─ tests/unit/
├─ charts/observatory/       # Helm chart (server only)
├─ action.yml                # composite GH Action
├─ tests/ (shared harnesses — golden/integration/mcp_contract)
└─ docs/superpowers/{specs,plans}/
```

One `release.yml` tag push builds both packages and uploads them as same-version PyPI releases.

### 4.2 DeployContext pattern (lifted + trimmed)

`observatory.core.context.ObservatoryContext` — same capability-guarded pattern as `DeployContext`. Capabilities: `{PROM, LLM}`. No K8s, no SQLite. Each tool declares `NEEDS` at module level; the CLI/MCP shims pass it when constructing the guarded view.

### 4.3 SDK integration

```python
from fastmcp import FastMCP
from observatory_sdk import instrument

server = FastMCP("my-server")
instrument(server, service_name="my-server", prometheus_port=9090)
# ... register tools as usual ...
server.run()
```

Under the hood `instrument()` replaces `server.tool` with a wrapped decorator so every *subsequently registered* tool emits:
- Span `mcp.tool.<name>` with attributes `mcp.service`, `mcp.tool`, `mcp.outcome`.
- Counter `mcp_tool_calls_total{service, tool, outcome}`.
- Histogram `mcp_tool_duration_seconds{service, tool, outcome}`.
- Gauge `mcp_tool_inflight{service, tool}`.

Labels are intentionally low-cardinality. `outcome` ∈ `{success, error, timeout}`.

If `prometheus_port` is set, the SDK starts a background HTTP server on that port serving `/metrics`. Otherwise, callers wire `metrics_asgi_app` into their own app.

`record_tool_call(service, tool, duration_s, outcome)` — low-level API for non-FastMCP servers.

### 4.4 Data flow — `detect_tool_abandonment`

Pure PromQL chain:

1. **Baseline rate** (7d) per `(service, tool)`:
   `avg_over_time(sum by (service, tool)(rate(mcp_tool_calls_total[10m]))[7d:10m])`.
2. **Current rate** (1h):
   `sum by (service, tool)(rate(mcp_tool_calls_total[1h]))`.
3. **Drop pct** = `(baseline - current) / baseline * 100`.
4. If `drop_pct ≥ 80` AND `baseline_rate ≥ 0.1` → candidate for `suspected`.
5. For each candidate, query **error spike** in the correlation window `[recorded_at - 60m, recorded_at - 10m]`:
   `max_over_time(sum by (service, tool)(rate(mcp_tool_calls_total{outcome="error"}[5m])[50m:5m]))`.
6. If error-spike > `baseline_error_rate + 0.01` absolute → `confirmed`. Else `suspected`.

All four PromQL queries live in `rules/abandonment.py` as string templates. Unit tests feed recorded Prom responses to a mock `PromAdapter` and assert signal outputs.

## 5. Data Model

```python
class Capability(StrEnum):
    PROM = "prom"
    LLM  = "llm"


class TimeSeries(BaseModel):
    promql: str
    start:  datetime
    end:    datetime
    step_s: float
    samples: list[tuple[datetime, float]]


class ServerHealth(BaseModel):
    service: str
    total_tools: int
    healthy_count: int
    degraded_count: int
    abandoned_count: int
    p99_latency_ms: float | None = None
    error_rate: float | None = None


class FleetHealth(BaseModel):
    servers: list[ServerHealth]
    last_updated: datetime


class AbandonmentSignal(BaseModel):
    service: str
    tool: str
    status: Literal["suspected", "confirmed"]
    baseline_rate: float
    current_rate: float
    drop_pct: float
    error_spike_at: datetime | None = None
    receipts: dict[str, Any] = Field(default_factory=dict)


class ServerComparison(BaseModel):
    service_a: str
    service_b: str
    window: str
    tools_a: int
    tools_b: int
    error_rate_a: float | None = None
    error_rate_b: float | None = None
    p99_latency_ms_a: float | None = None
    p99_latency_ms_b: float | None = None


class FleetHealthExplanation(BaseModel):
    overall: Literal["healthy", "degraded", "partial_outage", "unknown"]
    reasons: list[str]
    recommendations: list[str]
    evidence: dict[str, Any]
```

## 6. The 8 Tools

| # | Tool | Needs | Returns |
|---|---|---|---|
| 1 | `list_mcp_servers()` | PROM | `list[str]` of services seen in last 24h. |
| 2 | `get_tool_call_rate(service, tool?, window)` | PROM | `TimeSeries`. |
| 3 | `get_tool_error_rate(service, tool?, window)` | PROM | `TimeSeries`. |
| 4 | `get_tool_latency_p99(service, tool?, window)` | PROM | `TimeSeries`. |
| 5 | `get_fleet_health()` | PROM | `FleetHealth`. |
| 6 | `detect_tool_abandonment(service?, tool?)` | PROM | `list[AbandonmentSignal]`. |
| 7 | `compare_servers(service_a, service_b, window?)` | PROM | `ServerComparison`. |
| 8 | `explain_fleet_health()` | PROM + LLM | `FleetHealthExplanation` with deterministic offline fallback. |

Tool 6 is the hero feature. Tool 8 demonstrates the composition pattern (reuses tools 1+5+6 as evidence).

## 7. Surfaces

**CLI** (`deploy-intel`-style one-subcommand-per-tool):
- `observatory list-mcp-servers`
- `observatory get-tool-call-rate <service> [--tool X] [--window 1h]`
- `observatory detect-tool-abandonment [--service X] [--tool Y]`
- `observatory explain-fleet-health`
- `observatory serve-mcp`

Shared flags: `--prom-url`, `--llm-provider`, `--llm-base-url`, `--llm-api-key`, `--no-llm`, `--format json|md`.

**MCP server** (FastMCP 3.x): all 8 tools exposed with snake_case names matching the CLI.

**Helm chart** (`charts/observatory/`): Deployment + Service on port 8000 serving FastMCP-HTTP transport; ServiceMonitor + PrometheusRule guarded by `enabled: true` flags (default `false`).

**GitHub Action**: composite action for PR checks; runs `observatory detect-tool-abandonment` against a user-supplied Prom URL and fails on `confirmed` signals.

## 8. LLM Configuration

Same pattern as deploy-intel: litellm + instructor, provider-agnostic. Env vars: `OBSERVATORY_LLM_PROVIDER`, `OBSERVATORY_LLM_BASE_URL`, `OBSERVATORY_LLM_API_KEY`, `OBSERVATORY_OFFLINE`. Only `explain_fleet_health` uses the LLM — all other tools are pure PromQL.

## 9. Testing

Four-layer pyramid. **No kind dependency for the release gate.**

1. **Unit** — per tool + per rule, PromAdapter mocked, pytest-asyncio auto.
2. **Golden** — `tests/golden/<tool>/<scenario>/{input_prom.json, expected.json}`. A fake `PromAdapter` replays recorded responses. Deterministic. Runs in ~100ms.
3. **Integration** — spawn a tiny synthetic Prom server (python `http.server` or `aiohttp`) serving canned responses; run CLI subprocess; assert expected output.
4. **MCP stdio contract** — spawn `serve-mcp`, send JSON-RPC, assert 8 tool names returned.

**SDK tests** use a fresh `CollectorRegistry` per test; assert counter/histogram/gauge values after simulated call sequences. No kind, no Prom.

## 10. Abandonment detector — rule details

`rules/abandonment.py`:

```python
@dataclass
class AbandonmentThresholds:
    drop_pct: float = 80.0
    baseline_min_rate: float = 0.1
    error_rate_floor: float = 0.01

async def detect(prom: PromAdapter, *, service: str | None = None,
                 tool: str | None = None,
                 thresholds: AbandonmentThresholds = ...) -> list[AbandonmentSignal]: ...
```

Thresholds exposed as CLI flags (`--drop-pct`, `--baseline-min`, `--error-floor`) and as Helm values for the in-cluster default.

## 11. Release & Versioning

SemVer. `0.x.y` until the SDK is adopted by two sibling repos (prod-readiness + deploy-intel) and the abandonment detector + explain_fleet_health ship. Keep-a-Changelog. GitHub Release on tag: build both packages → PyPI publish × 2 → multi-arch image → cosign keyless sign → CycloneDX SBOM attached.

Phase milestones:
- `v0.1.0` — Walking skeleton: both packages + 2 tools + SDK `instrument()`.
- `v0.2.0` — 3 more query tools.
- `v0.3.0` — Abandonment detector (hero feature).
- `v0.4.0` — Fleet health + LLM explain.
- `v0.5.0` — SDK adoption in sibling repos (cross-repo PRs).
- `v1.0.0` — Helm chart + cluster matrix + workshop doc + production-ready.

## 12. Workshop Path (1–3 hr)

1. **(30 min)** Install observatory locally; point it at Prom; run the 8 tools against real sibling MCP servers.
2. **(45 min)** Simulate abandonment: skip one of prod-readiness's tools via `--check`; watch `detect_tool_abandonment` fire. Trigger errors; watch it escalate.
3. **(45 min)** Adopt the SDK in a NEW FastMCP server (3-line integration). Confirm it appears in `list_mcp_servers`.
4. **(15 min)** Install via Helm; wire `PrometheusRule` alerts to Alertmanager.

## 13. Open Decisions (all taken during brainstorming)

| Decision | Choice |
|---|---|
| MVP shape | Query-router + SDK (two PyPI packages) |
| Stack | Python-only |
| Abandonment detection | Frequency-deviation + error-correlation, pure PromQL |
| Monorepo layout | `packages/server/` + `packages/sdk/`, co-versioned tags |
| SDK API | One-line `instrument(server, service_name=..., prometheus_port=...)` |
| Tool count | 8 query tools |
| LLM usage | Only in `explain_fleet_health`; deterministic fallback offline |
| Kind in test pyramid | **Not required** — recorded Prom responses drive goldens |

## 14. Success Criteria (`v1.0.0` exit)

1. All 8 tools pass goldens + integration + mcp_contract in CI.
2. SDK `pip install mcp-observatory-sdk` + `instrument(server, service_name=...)` works from a 5-line test script.
3. Sibling repos (`mcp-prod-readiness` v1.1.0, `mcp-deploy-intel` v1.1.0) adopt the SDK and show up in `list_mcp_servers`.
4. Helm chart installs on kind + EKS/GKE/AKS (cluster-matrix CI).
5. Cosign signature validates on the pushed `v1.0.0` image.
6. Workshop doc validated — all 4 modules run without debugging.
7. Two PyPI packages published: `mcp-observatory==1.0.0`, `mcp-observatory-sdk==1.0.0`.
