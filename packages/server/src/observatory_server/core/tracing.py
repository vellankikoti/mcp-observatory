from __future__ import annotations

from opentelemetry import trace
from opentelemetry.trace import Tracer

_NAME = "observatory-server"


def tracer() -> Tracer:
    return trace.get_tracer(_NAME)
