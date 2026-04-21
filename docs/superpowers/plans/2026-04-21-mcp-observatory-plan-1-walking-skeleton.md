# mcp-observatory — Plan 1: Walking Skeleton + First 2 Tools

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** `v0.1.0` — scaffold the two-package monorepo, lift `PromAdapter` + `LLMAdapter` from deploy-intel, ship the SDK's `instrument(server, ...)` one-line API + ASGI `/metrics` endpoint, implement 2 query tools (`list_mcp_servers`, `get_tool_call_rate`), full CLI + MCP + cosign/SBOM release pipeline.

**Tech:** Python 3.11, `uv`, Typer, FastMCP 3.x, `prometheus_client`, `opentelemetry-api`, `pytest`. **No kind.**

**Working directory:** `02-mcp-observatory/`. Reference source to copy from: `../03-mcp-deploy-intel/` (release.yml, action.yml, conventions, adapters).

---

## Conventions (locked)

- `from __future__ import annotations`; `datetime.UTC`; `StrEnum`; unquoted forward refs.
- `ruff check` AND `ruff format --check` BOTH before every commit.
- `B008` ignored (Typer). Never add unused `noqa` (RUF100).
- Conventional Commits.
- Two `pyproject.toml` files (one per package) + a workspace root. Hatch build backend for both.
- SDK zero-dep: `prometheus_client>=0.20`, `opentelemetry-api>=1.25` ONLY.
- Server package depends on `mcp-observatory-sdk` (dogfoods it in v0.5.0+; in v0.1.0 the dep is declared but unused to lock the shape).

---

## Task 1 — Monorepo scaffolding

**Files:**
- Create: `02-mcp-observatory/pyproject.toml` — workspace root (pytest + ruff + mypy config only, no `[project]`).
- Create: `02-mcp-observatory/.gitignore`, `.python-version`, `README.md` (stub), `.pre-commit-config.yaml`.
- Create: `packages/server/pyproject.toml`, `packages/server/src/observatory/__init__.py` (`__version__ = "0.1.0"`), `packages/server/src/observatory/py.typed`, `packages/server/tests/__init__.py`.
- Create: `packages/sdk/pyproject.toml`, `packages/sdk/src/observatory_sdk/__init__.py` (`__version__ = "0.1.0"`), `packages/sdk/src/observatory_sdk/py.typed`, `packages/sdk/tests/__init__.py`.
- Create: `.github/workflows/ci.yml` — lint+format+mypy+pytest against both packages.

**Workspace root `pyproject.toml`:**
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "ASYNC", "RUF"]
ignore = ["E501", "B008"]

[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]
mypy_path = ["packages/server/src", "packages/sdk/src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["packages/server/tests", "packages/sdk/tests", "tests"]
addopts = "-ra --strict-markers"
markers = [
  "integration: tests requiring a synthetic Prom HTTP server",
  "golden: golden-test scenarios (recorded Prom responses)",
  "mcp_contract: MCP stdio contract tests",
]
```

**`packages/server/pyproject.toml`:**
```toml
[project]
name = "mcp-observatory"
version = "0.1.0"
description = "MCP query router for observability of distributed MCP server fleets."
readme = "../../README.md"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
authors = [{ name = "vellankikoti", email = "vellankikoti@gmail.com" }]
classifiers = [
  "Development Status :: 3 - Alpha",
  "License :: OSI Approved :: Apache Software License",
  "Programming Language :: Python :: 3.11",
  "Topic :: System :: Systems Administration",
]
dependencies = [
  "pydantic>=2.7",
  "httpx>=0.27",
  "typer>=0.12",
  "fastmcp>=3.0",
  "litellm>=1.40",
  "instructor>=1.3",
  "opentelemetry-api>=1.25",
  "rich>=13.7",
  "mcp-observatory-sdk>=0.1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "pytest-httpx>=0.30",
  "ruff>=0.4",
  "mypy>=1.10",
  "PyYAML>=6.0",
  "types-PyYAML",
]

[project.scripts]
observatory = "observatory.cli:app"
mcp-observatory = "observatory.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/observatory"]
```

**`packages/sdk/pyproject.toml`:**
```toml
[project]
name = "mcp-observatory-sdk"
version = "0.1.0"
description = "Tiny SDK that instruments MCP servers with Prometheus metrics + OpenTelemetry spans."
readme = "../../README.md"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
authors = [{ name = "vellankikoti", email = "vellankikoti@gmail.com" }]
classifiers = [
  "Development Status :: 3 - Alpha",
  "License :: OSI Approved :: Apache Software License",
  "Programming Language :: Python :: 3.11",
]
dependencies = [
  "prometheus-client>=0.20",
  "opentelemetry-api>=1.25",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "fastmcp>=3.0",       # only for integration tests of instrument()
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/observatory_sdk"]
```

**Bootstrap:**
```bash
cd 02-mcp-observatory
git init && git branch -M main
uv venv
# install both packages editable + dev deps:
uv pip install -e ./packages/sdk -e ./packages/server --group dev
# or a simpler path: install server which pulls sdk transitively, then dev extras:
uv pip install -e "packages/server[dev]" -e "packages/sdk[dev]"
```

**CI (`.github/workflows/ci.yml`):**
```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:
permissions: { contents: read }
jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv python install 3.11
      - run: uv venv
      - run: uv pip install -e "packages/sdk[dev]" -e "packages/server[dev]"
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy packages/server/src packages/sdk/src
      - run: uv run pytest -m "not integration and not golden and not mcp_contract" --cov
```

Verify with `uv run ruff check .`, `uv run mypy packages/server/src packages/sdk/src`, `uv run pytest --collect-only`. Commit: `chore: scaffold mcp-observatory monorepo (server + sdk)`.

---

## Task 2 — SDK: `metrics.py`, `tracing.py`, `instrument.py`, ASGI app

**Files:**
- Create: `packages/sdk/src/observatory_sdk/__init__.py` — public exports.
- Create: `packages/sdk/src/observatory_sdk/metrics.py` — module-level `CollectorRegistry` + counters/histogram/gauge + `record_tool_call(...)`.
- Create: `packages/sdk/src/observatory_sdk/tracing.py` — tracer helper.
- Create: `packages/sdk/src/observatory_sdk/instrument.py` — `instrument(server, *, service_name, prometheus_port=None, tool_filter=None)`.
- Create: `packages/sdk/src/observatory_sdk/asgi.py` — `metrics_asgi_app(registry)` returns an ASGI callable serving `/metrics`.
- Create: `packages/sdk/tests/unit/test_metrics.py`, `test_instrument.py`, `test_asgi.py`.

**`metrics.py`:**
```python
from __future__ import annotations

from enum import StrEnum
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class ToolCallOutcome(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


def new_registry() -> CollectorRegistry:
    return CollectorRegistry()


def build_instruments(registry: CollectorRegistry) -> tuple[Counter, Histogram, Gauge]:
    calls = Counter(
        "mcp_tool_calls_total",
        "Total MCP tool calls.",
        ["service", "tool", "outcome"],
        registry=registry,
    )
    duration = Histogram(
        "mcp_tool_duration_seconds",
        "MCP tool call duration in seconds.",
        ["service", "tool", "outcome"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        registry=registry,
    )
    inflight = Gauge(
        "mcp_tool_inflight",
        "Number of in-flight MCP tool calls.",
        ["service", "tool"],
        registry=registry,
    )
    return calls, duration, inflight


def record_tool_call(
    registry: CollectorRegistry,
    service: str,
    tool: str,
    duration_s: float,
    outcome: ToolCallOutcome,
) -> None:
    calls, duration, _ = build_instruments_cached(registry)
    calls.labels(service=service, tool=tool, outcome=outcome.value).inc()
    duration.labels(service=service, tool=tool, outcome=outcome.value).observe(duration_s)


_INSTRUMENTS_CACHE: dict[int, tuple[Counter, Histogram, Gauge]] = {}


def build_instruments_cached(registry: CollectorRegistry) -> tuple[Counter, Histogram, Gauge]:
    k = id(registry)
    if k not in _INSTRUMENTS_CACHE:
        _INSTRUMENTS_CACHE[k] = build_instruments(registry)
    return _INSTRUMENTS_CACHE[k]
```

**`tracing.py`:**
```python
from __future__ import annotations

from opentelemetry import trace


def tracer():
    return trace.get_tracer("mcp_observatory_sdk")
```

**`instrument.py`:**
```python
from __future__ import annotations

import functools
import time
from typing import Any, Callable

from prometheus_client import CollectorRegistry, start_http_server

from observatory_sdk.metrics import (
    ToolCallOutcome,
    build_instruments_cached,
    new_registry,
)
from observatory_sdk.tracing import tracer

_DEFAULT_REGISTRY: CollectorRegistry | None = None


def get_metrics_registry() -> CollectorRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = new_registry()
    return _DEFAULT_REGISTRY


def instrument(
    server: Any,
    *,
    service_name: str,
    prometheus_port: int | None = None,
    tool_filter: Callable[[str], bool] | None = None,
    registry: CollectorRegistry | None = None,
) -> None:
    """Patch `server.tool` so every subsequently registered tool emits metrics + spans."""
    reg = registry or get_metrics_registry()
    calls, duration, inflight = build_instruments_cached(reg)

    orig_tool = server.tool  # FastMCP's decorator factory

    def new_tool(*dargs, **dkwargs):
        decorator = orig_tool(*dargs, **dkwargs)

        def wrapper(fn):
            name = dkwargs.get("name") or fn.__name__
            if tool_filter is not None and not tool_filter(name):
                return decorator(fn)

            @functools.wraps(fn)
            async def observed(*args, **kwargs):
                outcome = ToolCallOutcome.SUCCESS
                start = time.perf_counter()
                inflight.labels(service=service_name, tool=name).inc()
                with tracer().start_as_current_span(f"mcp.tool.{name}") as span:
                    span.set_attribute("mcp.service", service_name)
                    span.set_attribute("mcp.tool", name)
                    try:
                        return await fn(*args, **kwargs)
                    except TimeoutError:
                        outcome = ToolCallOutcome.TIMEOUT
                        raise
                    except Exception:
                        outcome = ToolCallOutcome.ERROR
                        raise
                    finally:
                        dur = time.perf_counter() - start
                        calls.labels(service=service_name, tool=name, outcome=outcome.value).inc()
                        duration.labels(service=service_name, tool=name, outcome=outcome.value).observe(dur)
                        inflight.labels(service=service_name, tool=name).dec()
                        span.set_attribute("mcp.outcome", outcome.value)

            return decorator(observed)

        return wrapper

    server.tool = new_tool

    if prometheus_port is not None:
        start_http_server(prometheus_port, registry=reg)
```

**`asgi.py`:**
```python
from __future__ import annotations

from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST


def metrics_asgi_app(registry: CollectorRegistry):
    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        body = generate_latest(registry)
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", CONTENT_TYPE_LATEST.encode())],
        })
        await send({"type": "http.response.body", "body": body})
    return app
```

**`__init__.py`:**
```python
from observatory_sdk.instrument import instrument, get_metrics_registry
from observatory_sdk.metrics import ToolCallOutcome, record_tool_call, new_registry
from observatory_sdk.asgi import metrics_asgi_app
from observatory_sdk.tracing import tracer

__version__ = "0.1.0"
__all__ = [
    "instrument",
    "record_tool_call",
    "ToolCallOutcome",
    "new_registry",
    "get_metrics_registry",
    "metrics_asgi_app",
    "tracer",
]
```

**Unit tests** (~8 total):

1. `test_metrics_record_tool_call_increments_counter` — use a fresh `CollectorRegistry`; call `record_tool_call(reg, "s", "t", 0.1, SUCCESS)` twice; scrape via `generate_latest(reg)`; assert `mcp_tool_calls_total{service="s",tool="t",outcome="success"} == 2`.
2. `test_metrics_outcome_values` — 3 enum values.
3. `test_instrument_wraps_and_counts_success` — create a real `FastMCP("test")`; call `instrument(server, service_name="x", registry=reg)`; register a tool via `@server.tool()`; call it; assert counter = 1, histogram observations ≥ 1, inflight = 0.
4. `test_instrument_wraps_and_counts_error` — tool that raises; assert counter increments with `outcome="error"`; exception propagates.
5. `test_instrument_tool_filter_skips` — `tool_filter=lambda name: name != "skip_me"`; register both; only `do_me` is wrapped.
6. `test_instrument_prometheus_port_starts_server` (optional — tests with `start_http_server` are flaky; skip this test's HTTP binding and just assert `instrument(..., prometheus_port=None)` doesn't start a server; port=9199 tested via ASGI app instead).
7. `test_asgi_metrics_app_returns_prom_format` — use httpx `ASGITransport` on `metrics_asgi_app(reg)`; GET `/metrics`; assert 200, content-type, body contains `mcp_tool_calls_total`.
8. `test_tracer_emits_span` — configure in-memory span exporter; call tracer().start_as_current_span; assert 1 span emitted.

Commit: `feat(sdk): metrics + instrument() + ASGI /metrics + tracing helper`.

---

## Task 3 — Server package: adapters + context + models

Port from deploy-intel:
- `packages/server/src/observatory/adapters/prom.py` — verbatim lift.
- `packages/server/src/observatory/adapters/llm.py` — verbatim lift, env var rename `DEPLOY_INTEL_*` → `OBSERVATORY_*`.
- `packages/server/src/observatory/core/tracing.py` — lift, `_NAME = "observatory"`.
- `packages/server/src/observatory/core/models.py` — NEW. Define `Capability`, `TimeSeries`, `ServerHealth`, `FleetHealth`, `AbandonmentSignal`, `ServerComparison`, `FleetHealthExplanation` per spec §5.
- `packages/server/src/observatory/core/context.py` — NEW. `ObservatoryContext` dataclass with `prom: PromAdapter`, `llm: LLMAdapter` + `GuardedContext` (only `PROM` + `LLM` capabilities).

**Unit tests** (~6 total):
- `test_models_basic.py` — 2: TimeSeries round-trip; AbandonmentSignal defaults.
- `test_context.py` — 2: guard blocks undeclared; `PROM` works when declared.
- `test_prom_adapter.py` — 2: instant query returns parsed data; unavailable when `base_url=None`.

Commit: `feat(core): adapters + ObservatoryContext + models`.

---

## Task 4 — First tool: `list_mcp_servers`

**Files:**
- Create: `packages/server/src/observatory/tools/__init__.py` (empty)
- Create: `packages/server/src/observatory/tools/list_mcp_servers.py`
- Create: `packages/server/tests/unit/test_tool_list_mcp_servers.py`

**Tool:**
```python
from __future__ import annotations

from deploy_intel_like  # NOTE: do not copy — observatory has no deploy_intel dependency

# Actual imports:
from observatory.core.context import GuardedContext
from observatory.core.models import Capability
from observatory.core.tracing import tracer

NEEDS = frozenset({Capability.PROM})


async def list_mcp_servers(ctx: GuardedContext, window: str = "24h") -> list[str]:
    """Return the set of service label values seen in mcp_tool_calls_total over `window`."""
    with tracer().start_as_current_span("tool.list_mcp_servers") as span:
        span.set_attribute("tool.name", "list_mcp_servers")
        span.set_attribute("window", window)
        promql = f'count by (service)(count_over_time(mcp_tool_calls_total[{window}]))'
        data = await ctx.prom.query(promql)
        services = sorted({
            s.get("metric", {}).get("service", "unknown")
            for s in (data.get("result") or [])
            if s.get("metric", {}).get("service")
        })
        span.set_attribute("services", len(services))
        return services
```

**Unit tests** (3):
- `test_returns_unique_services` — mock `ctx.prom.query` to return 2 distinct `service` labels → returns 2-element sorted list.
- `test_empty_result_returns_empty_list` — empty result → `[]`.
- `test_duplicates_deduped` — same service listed twice in result → single entry.

Commit: `feat(tools): list_mcp_servers`.

---

## Task 5 — Second tool: `get_tool_call_rate`

**Files:** `tools/get_tool_call_rate.py` + test file.

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from observatory.core.context import GuardedContext
from observatory.core.models import Capability, TimeSeries
from observatory.core.tracing import tracer

NEEDS = frozenset({Capability.PROM})

_WINDOW_RE = __import__("re").compile(r"^(?P<n>\d+)(?P<unit>[smhd])$")


def _parse_window(window: str) -> timedelta:
    m = _WINDOW_RE.match(window)
    if m is None:
        raise ValueError(f"invalid window: {window}")
    n = int(m.group("n"))
    return {"s": timedelta(seconds=n), "m": timedelta(minutes=n),
            "h": timedelta(hours=n), "d": timedelta(days=n)}[m.group("unit")]


async def get_tool_call_rate(
    ctx: GuardedContext,
    service: str,
    tool: str | None = None,
    window: str = "1h",
) -> TimeSeries:
    with tracer().start_as_current_span("tool.get_tool_call_rate") as span:
        span.set_attribute("tool.name", "get_tool_call_rate")
        span.set_attribute("service", service)
        span.set_attribute("window", window)
        delta = _parse_window(window)
        end = datetime.now(UTC)
        start = end - delta
        step = max(15.0, delta.total_seconds() / 300)
        if tool:
            promql = (
                f'sum(rate(mcp_tool_calls_total{{service="{service}",tool="{tool}"}}[5m]))'
            )
        else:
            promql = f'sum(rate(mcp_tool_calls_total{{service="{service}"}}[5m]))'
        data = await ctx.prom.query_range(promql, start.timestamp(), end.timestamp(), step)
        samples: list[tuple[datetime, float]] = []
        for series in data.get("result") or []:
            for ts, raw in series.get("values", []):
                try:
                    samples.append((datetime.fromtimestamp(float(ts), UTC), float(raw)))
                except (TypeError, ValueError):
                    continue
        return TimeSeries(promql=promql, start=start, end=end, step_s=step, samples=samples)
```

**Unit tests (3)** — happy path with service only; service+tool; invalid window → raises.

Commit: `feat(tools): get_tool_call_rate`.

---

## Task 6 — CLI + MCP surfaces

**Files:**
- Create: `packages/server/src/observatory/cli.py` — Typer app with 3 commands (`list-mcp-servers`, `get-tool-call-rate`, `serve-mcp`).
- Create: `packages/server/src/observatory/mcp_server.py` — FastMCP with 2 tool registrations.
- Create: `packages/server/src/observatory/reports/json.py`, `markdown.py` — lift from deploy-intel.
- Create: `packages/server/tests/unit/test_cli.py` — 3 help-line tests (COLUMNS=200 / NO_COLOR=1 / TERM=dumb autouse fixture + ANSI strip).
- Create: `packages/server/tests/unit/test_mcp_server_smoke.py` — assert 2 tools exposed.

Commits (2):
- `feat(reports): JSON + Markdown renderers`.
- `feat(cli+mcp): surfaces for list_mcp_servers + get_tool_call_rate`.

---

## Task 7 — Golden harness (no kind!)

The harness replays recorded Prom responses via a fake PromAdapter. Fixtures live under `tests/golden/<tool>/<scenario>/{input_prom.json, expected.json}`.

**Files:**
- Create: `tests/golden/__init__.py`
- Create: `tests/golden/_runner.py` — `FakePromAdapter` that returns `input_prom.json` for `query()`/`query_range()`, plus `run_tool(tool_name, **args)` dispatcher.
- Create: `tests/golden/test_golden.py` — parametrized auto-discovery.
- Create: `tests/golden/list_mcp_servers/two-servers/input_prom.json` + `expected.json` + `meta.json`.
- Create: `tests/golden/list_mcp_servers/empty/input_prom.json` + `expected.json` + `meta.json`.
- Create: `tests/golden/get_tool_call_rate/one-series/input_prom.json` + `expected.json` + `meta.json`.

Each `meta.json`: `{"tool": "list_mcp_servers", "args": {}}` or `{"tool": "get_tool_call_rate", "args": {"service": "x", "tool": "y", "window": "1h"}}`.

`input_prom.json`: the full body `PromAdapter.query`/`query_range` would return: `{"result": [...], "resultType": "vector"}`.

Runtime: ~100ms total. No Docker. No kind.

Commit: `test(golden): recorded-Prom harness + 3 scenarios`.

---

## Task 8 — Integration + MCP contract

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_cli_vs_synthetic_prom.py` — starts a python `aiohttp` (or `http.server` in a thread) synthetic Prom on a random port returning canned JSON; runs `observatory list-mcp-servers --prom-url http://127.0.0.1:<port>`; asserts output.
- Create: `tests/mcp/__init__.py`
- Create: `tests/mcp/test_stdio_contract.py` — spawn `observatory serve-mcp`, JSON-RPC initialize + tools/list, assert 2 tool names.

Commit: `test: integration + MCP stdio contract (synthetic Prom)`.

---

## Task 9 — OTel tracing + Dockerfile + Helm skeleton + Action

**Files:**
- Modify tools to wrap with `tracer().start_as_current_span(...)` — already shown above; add `test_tracing.py` unit test.
- Create: `Dockerfile` (multi-stage, non-root; observatory entrypoint, installs BOTH packages).
- Create: `.dockerignore`
- Create: `charts/observatory/Chart.yaml`, `values.yaml`, `templates/_helpers.tpl`, `templates/serviceaccount.yaml`, `templates/clusterrole.yaml`, `templates/clusterrolebinding.yaml`, `templates/deployment.yaml`, `templates/service.yaml`, `templates/NOTES.txt`, `.helmignore`.
- Create: `action.yml` — composite action at repo root; mirror deploy-intel's shape.
- Create: `tests/action/__init__.py`, `tests/action/test_action_metadata.py` — 4 tests.
- Create: `tests/helm/__init__.py`, `tests/helm/test_helm_render.py` — 2 tests (lint clean; Deployment has 1 container).

Commit: `chore: Dockerfile + Helm chart skeleton + composite GH Action`.

---

## Task 10 — Release v0.1.0

**Files:**
- Create: `.github/workflows/release.yml` — **builds BOTH packages**:
  ```yaml
  pypi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv python install 3.11
      - run: uv venv
      - run: uv pip install build
      - name: Build sdk
        run: uv run python -m build packages/sdk --outdir dist-sdk
      - name: Build server
        run: uv run python -m build packages/server --outdir dist-server
      - uses: pypa/gh-action-pypi-publish@release/v1
        with: { packages-dir: dist-sdk }
      - uses: pypa/gh-action-pypi-publish@release/v1
        with: { packages-dir: dist-server }
  image: ... (cosign + sbom — lift verbatim from deploy-intel)
  ```
- Create: `CHANGELOG.md` — `[0.1.0]` entry.
- Modify: `README.md` — full install + quickstart (both packages).
- Create: `tests/workflows/test_release_workflow.py` — 2 tests (both sdk + server build steps present; cosign + sbom present).

Full release gate (no kind):
```
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/server/src packages/sdk/src
uv run pytest -m "not integration and not golden and not mcp_contract" -v
uv run pytest -m golden -v
uv run pytest -m integration -v
uv run pytest -m mcp_contract -v
uv run pytest tests/helm/ -v
uv run pytest tests/action/ -v
helm lint charts/observatory
```

Commit: `chore(release): v0.1.0 — walking skeleton + 2 tools + SDK`.

Deferred tag: `git tag -a v0.1.0 -m "v0.1.0"` → user runs after creating the repo + 2 PyPI pending publishers (one per package).

**IMPORTANT FOR PYPI SETUP:** two pending publishers are needed: one for `mcp-observatory` and one for `mcp-observatory-sdk`. Both use workflow `release.yml`. Document in the deferred-commands section.

---

## Plan 1 exit

- Two PyPI packages on PyPI
- Multi-arch image on GHCR, cosign-signed
- GitHub Release with SBOM
- 2 query tools + SDK `instrument()` working in a 3-line Python test script
- Helm chart lint-clean

Next plan: 3 more query tools (`get_tool_error_rate`, `get_tool_latency_p99`, `compare_servers`) → `v0.2.0`.
