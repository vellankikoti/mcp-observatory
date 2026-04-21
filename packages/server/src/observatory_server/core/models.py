from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Capability(StrEnum):
    PROM = "prom"
    LLM = "llm"


class TimeSeries(BaseModel):
    promql: str
    start: datetime
    end: datetime
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
    reasons: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
