# Changelog

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] — 2026-04-20 — detect_tool_abandonment (hero feature)

### Added
- `detect_tool_abandonment(service?, tool?, drop_pct, baseline_min_rate, error_rate_floor)` — hero feature that detects tools agents may have silently stopped using.
- `rules/abandonment.py` — standalone detection algorithm using four PromQL queries: 7d baseline rate, 1h current rate, 50m error spike, 7d baseline error rate.
- `AbandonmentThresholds` dataclass with configurable `drop_pct` (default 80%), `baseline_min_rate` (default 0.1 rps), and `error_rate_floor` (default 0.01 rps).
- Signals return `status="suspected"` (drop without error spike) or `status="confirmed"` (drop correlated with error spike ≥ 2× baseline).
- CLI subcommand `detect-tool-abandonment` with `--service`, `--tool`, `--drop-pct`, `--baseline-min`, `--error-floor` flags (6 subcommands total).
- MCP stdio server now exposes 6 tools (up from 5).
- Enhanced `FakePromAdapter` in the golden test runner to support substring-keyed `"queries"` array in `input_prom.json` (legacy `"query"` key still works).
- 2 new golden scenarios: `detect_tool_abandonment/two-suspected` and `detect_tool_abandonment/none-because-baseline-too-low`.
- 7 new unit tests: 5 rule tests + 2 tool-wrapper tests (60 total, up from 50).

## [0.2.0] — 2026-04-20 — 3 more query tools

### Added
- `get_tool_error_rate(service, tool?, window)` — ratio of `outcome="error"` calls to total over a range window using PromQL range queries.
- `get_tool_latency_p99(service, tool?, window)` — p99 latency TimeSeries via `histogram_quantile(0.99, ...)` on `mcp_tool_duration_seconds_bucket`.
- `compare_servers(service_a, service_b, window)` — instant-query comparison of two services returning `ServerComparison` with tool count, error rate, and p99 latency.
- CLI subcommands: `get-tool-error-rate`, `get-tool-latency-p99`, `compare-servers` (5 subcommands total).
- MCP stdio server now exposes 5 tools (up from 2).
- Shared `_util.py` with `_parse_window` helper (DRY refactor across all tools).
- 9 new unit tests for the 3 tools; 3 new CLI help tests; MCP smoke test updated to expect 5 tools.

## [0.1.0] — 2026-04-21 — walking skeleton

### Added
- Monorepo scaffolding with TWO PyPI packages: `mcp-observatory` (server+CLI) and `mcp-observatory-sdk` (instrumentation SDK).
- SDK: `instrument(server, service_name=...)` one-line FastMCP integration; `record_tool_call(...)` low-level API; `metrics_asgi_app` ASGI `/metrics` endpoint; `ToolCallOutcome` StrEnum; `prometheus_client` + `opentelemetry-api` only deps.
- Server: 2 query tools — `list_mcp_servers` and `get_tool_call_rate` — plus CLI + MCP stdio surfaces.
- Adapters: PromAdapter + LLMAdapter lifted from mcp-deploy-intel.
- Golden tests use recorded Prom responses — no kind dependency.
- Integration test uses a python http.server synthetic Prom.
- Release pipeline: both packages to PyPI, multi-arch image to GHCR with cosign keyless + CycloneDX SBOM.
