from __future__ import annotations

from observatory_sdk.metrics import ToolCallOutcome, new_registry, record_tool_call
from prometheus_client import generate_latest


def test_metrics_record_tool_call_increments_counter() -> None:
    reg = new_registry()
    record_tool_call(reg, "s", "t", 0.1, ToolCallOutcome.SUCCESS)
    record_tool_call(reg, "s", "t", 0.2, ToolCallOutcome.SUCCESS)
    body = generate_latest(reg).decode()
    assert 'mcp_tool_calls_total{outcome="success",service="s",tool="t"} 2.0' in body


def test_metrics_outcome_values() -> None:
    assert ToolCallOutcome.SUCCESS == "success"
    assert ToolCallOutcome.ERROR == "error"
    assert ToolCallOutcome.TIMEOUT == "timeout"


def test_metrics_histogram_observed() -> None:
    reg = new_registry()
    record_tool_call(reg, "svc", "my_tool", 0.05, ToolCallOutcome.SUCCESS)
    body = generate_latest(reg).decode()
    assert "mcp_tool_duration_seconds" in body
    assert 'service="svc"' in body
    assert 'tool="my_tool"' in body
