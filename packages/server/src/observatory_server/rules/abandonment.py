from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from observatory_server.core.models import AbandonmentSignal


@dataclass
class AbandonmentThresholds:
    drop_pct: float = 80.0
    baseline_min_rate: float = 0.1
    error_rate_floor: float = 0.01


_BASELINE_PROMQL = "avg_over_time(sum by (service, tool)(rate(mcp_tool_calls_total[10m]))[7d:10m])"
_CURRENT_PROMQL = "sum by (service, tool)(rate(mcp_tool_calls_total[1h]))"
_ERROR_SPIKE_PROMQL = (
    'max_over_time(sum by (service, tool)(rate(mcp_tool_calls_total{outcome="error"}[5m]))[50m:5m])'
)
_BASELINE_ERROR_PROMQL = (
    "avg_over_time("
    'sum by (service, tool)(rate(mcp_tool_calls_total{outcome="error"}[10m]))'
    "[7d:10m]"
    ")"
)


def _vector_to_map(data: dict[str, Any]) -> dict[tuple[str, str], float]:
    """Turn a Prom vector result into {(service, tool): scalar}."""
    out: dict[tuple[str, str], float] = {}
    for s in data.get("result") or []:
        m = s.get("metric") or {}
        service = m.get("service")
        tool = m.get("tool")
        if not service or not tool:
            continue
        try:
            out[(service, tool)] = float(s["value"][1])
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return out


async def detect(
    prom: Any,
    *,
    service: str | None = None,
    tool: str | None = None,
    thresholds: AbandonmentThresholds | None = None,
) -> list[AbandonmentSignal]:
    thresholds = thresholds or AbandonmentThresholds()

    baseline_data = await prom.query(_BASELINE_PROMQL)
    current_data = await prom.query(_CURRENT_PROMQL)
    baseline = _vector_to_map(baseline_data)
    current = _vector_to_map(current_data)

    signals: list[AbandonmentSignal] = []
    for key, baseline_rate in baseline.items():
        svc, tl = key
        if service and service != svc:
            continue
        if tool and tool != tl:
            continue
        if baseline_rate < thresholds.baseline_min_rate:
            continue
        current_rate = current.get(key, 0.0)
        drop_pct = (
            ((baseline_rate - current_rate) / baseline_rate) * 100.0 if baseline_rate > 0 else 0.0
        )
        if drop_pct < thresholds.drop_pct:
            continue

        # Candidate — check error spike
        error_spike_data = await prom.query(_ERROR_SPIKE_PROMQL)
        baseline_err_data = await prom.query(_BASELINE_ERROR_PROMQL)
        error_spike_map = _vector_to_map(error_spike_data)
        baseline_err_map = _vector_to_map(baseline_err_data)
        error_spike = error_spike_map.get(key, 0.0)
        baseline_err = baseline_err_map.get(key, 0.0)

        status_str: str = "suspected"
        error_spike_at: datetime | None = None
        if error_spike >= thresholds.error_rate_floor and error_spike >= 2 * max(
            baseline_err, thresholds.error_rate_floor
        ):
            status_str = "confirmed"
            error_spike_at = datetime.now(UTC) - timedelta(minutes=30)

        status = cast(Literal["suspected", "confirmed"], status_str)

        signals.append(
            AbandonmentSignal(
                service=svc,
                tool=tl,
                status=status,
                baseline_rate=baseline_rate,
                current_rate=current_rate,
                drop_pct=round(drop_pct, 2),
                error_spike_at=error_spike_at,
                receipts={
                    "baseline_rate": baseline_rate,
                    "current_rate": current_rate,
                    "error_spike": error_spike,
                    "baseline_error_rate": baseline_err,
                    "thresholds": {
                        "drop_pct": thresholds.drop_pct,
                        "baseline_min_rate": thresholds.baseline_min_rate,
                        "error_rate_floor": thresholds.error_rate_floor,
                    },
                },
            )
        )
    return signals
