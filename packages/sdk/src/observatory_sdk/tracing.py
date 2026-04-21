from __future__ import annotations

from opentelemetry import trace


def tracer() -> trace.Tracer:
    return trace.get_tracer("mcp_observatory_sdk")
