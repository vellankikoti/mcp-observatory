from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from observatory.core.context import ObservatoryContext
from observatory.tools.compare_servers import NEEDS, compare_servers


def _ctx(side_effects: list) -> ObservatoryContext:
    prom = MagicMock()
    prom.query = AsyncMock(side_effect=side_effects)
    return ObservatoryContext(prom=prom, llm=MagicMock())


def _vector(value: str) -> dict:
    """Minimal instant-query result payload."""
    return {"result": [{"metric": {}, "value": [0, value]}]}


@pytest.mark.asyncio
async def test_happy_path_populates_all_fields() -> None:
    # Order: tools_a, err_a, p99_a, tools_b, err_b, p99_b
    effects = [
        _vector("3"),
        _vector("0.05"),
        _vector("250.0"),
        _vector("5"),
        _vector("0.02"),
        _vector("180.0"),
    ]
    ctx = _ctx(effects).guard(needs=NEEDS)
    result = await compare_servers(ctx, service_a="svc-a", service_b="svc-b")
    assert result.service_a == "svc-a"
    assert result.service_b == "svc-b"
    assert result.tools_a == 3
    assert result.tools_b == 5
    assert result.error_rate_a == pytest.approx(0.05)
    assert result.error_rate_b == pytest.approx(0.02)
    assert result.p99_latency_ms_a == pytest.approx(250.0)
    assert result.p99_latency_ms_b == pytest.approx(180.0)


@pytest.mark.asyncio
async def test_exception_in_query_yields_none_field() -> None:
    effects = [
        _vector("2"),
        RuntimeError("prom down"),  # err_a fails
        _vector("100.0"),
        _vector("4"),
        _vector("0.01"),
        _vector("90.0"),
    ]
    ctx = _ctx(effects).guard(needs=NEEDS)
    result = await compare_servers(ctx, service_a="svc-a", service_b="svc-b")
    assert result.error_rate_a is None  # exception -> None
    assert result.tools_a == 2
    assert result.tools_b == 4


@pytest.mark.asyncio
async def test_invalid_window_raises_value_error() -> None:
    ctx = _ctx([]).guard(needs=NEEDS)
    with pytest.raises(ValueError, match="invalid window"):
        await compare_servers(ctx, service_a="a", service_b="b", window="bad")
