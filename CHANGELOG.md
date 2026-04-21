# Changelog

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-04-21 — walking skeleton

### Added
- Monorepo scaffolding with TWO PyPI packages: `mcp-observatory` (server+CLI) and `mcp-observatory-sdk` (instrumentation SDK).
- SDK: `instrument(server, service_name=...)` one-line FastMCP integration; `record_tool_call(...)` low-level API; `metrics_asgi_app` ASGI `/metrics` endpoint; `ToolCallOutcome` StrEnum; `prometheus_client` + `opentelemetry-api` only deps.
- Server: 2 query tools — `list_mcp_servers` and `get_tool_call_rate` — plus CLI + MCP stdio surfaces.
- Adapters: PromAdapter + LLMAdapter lifted from mcp-deploy-intel.
- Golden tests use recorded Prom responses — no kind dependency.
- Integration test uses a python http.server synthetic Prom.
- Release pipeline: both packages to PyPI, multi-arch image to GHCR with cosign keyless + CycloneDX SBOM.
