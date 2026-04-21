from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from observatory.rules.abandonment import AbandonmentThresholds, detect


def _vector(service: str, tool: str, value: str) -> dict:
    return {"result": [{"metric": {"service": service, "tool": tool}, "value": [0, value]}]}


def _empty() -> dict:
    return {"result": []}


def _make_prom(*side_effects: dict) -> MagicMock:
    prom = MagicMock()
    prom.query = AsyncMock(side_effect=list(side_effects))
    return prom


@pytest.mark.asyncio
async def test_no_signals_when_baseline_below_min() -> None:
    # baseline rate 0.05 < 0.1 minimum — should produce no candidates
    prom = _make_prom(
        _vector("svc", "t1", "0.05"),  # baseline
        _vector("svc", "t1", "0.0"),  # current
    )
    result = await detect(prom)
    assert result == []


@pytest.mark.asyncio
async def test_suspected_when_drop_pct_exceeds_threshold_no_error_spike() -> None:
    # baseline 2.0, current 0.2 → 90% drop; no error spike → suspected
    prom = _make_prom(
        _vector("svc", "t1", "2.0"),  # baseline
        _vector("svc", "t1", "0.2"),  # current
        _empty(),  # error_spike
        _empty(),  # baseline_error
    )
    result = await detect(prom)
    assert len(result) == 1
    sig = result[0]
    assert sig.status == "suspected"
    assert sig.error_spike_at is None
    assert sig.drop_pct == pytest.approx(90.0)


@pytest.mark.asyncio
async def test_confirmed_when_drop_correlates_with_error_spike() -> None:
    # baseline 2.0, current 0.2 → 90% drop
    # error_spike 0.05, baseline_err 0.005
    # 0.05 >= 0.01 (floor) and 0.05 >= 2 * max(0.005, 0.01) = 0.02 → confirmed
    prom = _make_prom(
        _vector("svc", "t1", "2.0"),  # baseline
        _vector("svc", "t1", "0.2"),  # current
        _vector("svc", "t1", "0.05"),  # error_spike
        _vector("svc", "t1", "0.005"),  # baseline_error
    )
    result = await detect(prom)
    assert len(result) == 1
    sig = result[0]
    assert sig.status == "confirmed"
    assert isinstance(sig.error_spike_at, datetime)


@pytest.mark.asyncio
async def test_service_filter_drops_other_services() -> None:
    # baseline has two (service, tool) pairs; filter to s1 only
    prom = MagicMock()
    prom.query = AsyncMock(
        side_effect=[
            {
                "result": [
                    {"metric": {"service": "s1", "tool": "t1"}, "value": [0, "2.0"]},
                    {"metric": {"service": "s2", "tool": "t2"}, "value": [0, "2.0"]},
                ]
            },  # baseline
            {"result": []},  # current (both drop to 0 → 100%)
            _empty(),  # error_spike for s1 candidate
            _empty(),  # baseline_error for s1 candidate
        ]
    )
    result = await detect(prom, service="s1")
    assert len(result) == 1
    assert result[0].service == "s1"


@pytest.mark.asyncio
async def test_custom_thresholds_applied() -> None:
    # 60% drop — default threshold 80% wouldn't trigger, but drop_pct=50 should
    prom = _make_prom(
        _vector("svc", "t1", "2.0"),  # baseline
        _vector("svc", "t1", "0.8"),  # current → 60% drop
        _empty(),  # error_spike
        _empty(),  # baseline_error
    )
    result = await detect(prom, thresholds=AbandonmentThresholds(drop_pct=50.0))
    assert len(result) == 1
    assert result[0].drop_pct == pytest.approx(60.0)
