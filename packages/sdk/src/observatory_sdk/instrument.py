from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

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

    def new_tool(*dargs: Any, **dkwargs: Any) -> Callable[[Any], Any]:
        decorator = orig_tool(*dargs, **dkwargs)

        def wrapper(fn: Any) -> Any:
            name = dkwargs.get("name") or fn.__name__
            if tool_filter is not None and not tool_filter(name):
                return decorator(fn)

            @functools.wraps(fn)
            async def observed(*args: Any, **kwargs: Any) -> Any:
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
                        duration.labels(
                            service=service_name, tool=name, outcome=outcome.value
                        ).observe(dur)
                        inflight.labels(service=service_name, tool=name).dec()
                        span.set_attribute("mcp.outcome", outcome.value)

            return decorator(observed)

        return wrapper

    server.tool = new_tool

    if prometheus_port is not None:
        start_http_server(prometheus_port, registry=reg)
