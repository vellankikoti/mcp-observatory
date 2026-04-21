from __future__ import annotations

import re

import pytest
from observatory_server.cli import app
from typer.testing import CliRunner

runner = CliRunner()
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(s: str) -> str:
    return re.sub(r"\s+", " ", _ANSI.sub("", s)).lower().strip()


@pytest.fixture(autouse=True)
def _wide_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")


def test_help_mentions_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    for cmd in (
        "list-mcp-servers",
        "get-tool-call-rate",
        "get-tool-error-rate",
        "get-tool-latency-p99",
        "compare-servers",
        "detect-tool-abandonment",
        "get-fleet-health",
        "explain-fleet-health",
        "serve-mcp",
        "serve-http",
        "verify-services",
    ):
        assert cmd.replace("-", "") in out.replace("-", "")


def test_list_mcp_servers_help_has_window_and_prom_url_flags() -> None:
    result = runner.invoke(app, ["list-mcp-servers", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "window" in collapsed
    assert "prom" in collapsed
    assert "format" in collapsed


def test_get_tool_call_rate_help_has_service_and_tool_flags() -> None:
    result = runner.invoke(app, ["get-tool-call-rate", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "service" in collapsed
    assert "tool" in collapsed
    assert "window" in collapsed


def test_get_tool_error_rate_help_has_service_and_tool_flags() -> None:
    result = runner.invoke(app, ["get-tool-error-rate", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "service" in collapsed
    assert "tool" in collapsed
    assert "window" in collapsed


def test_get_tool_latency_p99_help_has_service_and_tool_flags() -> None:
    result = runner.invoke(app, ["get-tool-latency-p99", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "service" in collapsed
    assert "tool" in collapsed
    assert "window" in collapsed


def test_compare_servers_help_has_service_a_b_flags() -> None:
    result = runner.invoke(app, ["compare-servers", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "service" in collapsed
    assert "window" in collapsed


def test_detect_tool_abandonment_help_has_expected_flags() -> None:
    result = runner.invoke(app, ["detect-tool-abandonment", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "service" in collapsed
    assert "tool" in collapsed
    assert "drop" in collapsed


def test_serve_http_help_has_port_flag() -> None:
    result = runner.invoke(app, ["serve-http", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "port" in collapsed


def test_verify_services_help_has_expected_flag() -> None:
    result = runner.invoke(app, ["verify-services", "--help"])
    assert result.exit_code == 0
    collapsed = _plain(result.output)
    assert "expected" in collapsed
    assert "window" in collapsed
