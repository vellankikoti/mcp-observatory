from __future__ import annotations

from datetime import UTC, datetime

from observatory_server.core.models import AbandonmentSignal, TimeSeries


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC)


def test_time_series_roundtrip() -> None:
    now = _dt(1_700_000_000)
    later = _dt(1_700_003_600)
    ts = TimeSeries(
        promql='up{job="mcp"}',
        start=now,
        end=later,
        step_s=60.0,
        samples=[(now, 1.0), (later, 0.0)],
    )
    dumped = ts.model_dump()
    restored = TimeSeries.model_validate(dumped)
    assert restored.promql == ts.promql
    assert restored.step_s == 60.0
    assert len(restored.samples) == 2


def test_abandonment_signal_defaults() -> None:
    sig = AbandonmentSignal(
        service="svc-a",
        tool="tool_x",
        status="suspected",
        baseline_rate=0.8,
        current_rate=0.1,
        drop_pct=87.5,
    )
    assert sig.receipts == {}
    assert sig.error_spike_at is None
