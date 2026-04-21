from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from observatory.core.context import ObservatoryContext
from observatory.core.models import Capability
from observatory.rules.abandonment import AbandonmentThresholds
from observatory.tools.detect_tool_abandonment import NEEDS, detect_tool_abandonment


def _ctx() -> ObservatoryContext:
    prom = MagicMock()
    prom.query = AsyncMock(return_value={"result": []})
    return ObservatoryContext(prom=prom, llm=MagicMock())


def test_needs_is_prom_only() -> None:
    assert frozenset({Capability.PROM}) == NEEDS


@pytest.mark.asyncio
async def test_forwards_thresholds_to_detect() -> None:
    ctx = _ctx().guard(needs=NEEDS)
    mock_detect = AsyncMock(return_value=[])
    with patch("observatory.tools.detect_tool_abandonment.detect", mock_detect):
        await detect_tool_abandonment(ctx, service="s", tool="t", drop_pct=50.0)

    mock_detect.assert_awaited_once()
    _, kwargs = mock_detect.call_args
    thresholds = kwargs["thresholds"]
    assert isinstance(thresholds, AbandonmentThresholds)
    assert thresholds.drop_pct == pytest.approx(50.0)
