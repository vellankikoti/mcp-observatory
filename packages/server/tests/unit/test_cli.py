from __future__ import annotations

import re

import pytest
from observatory.cli import app
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
    for cmd in ("list-mcp-servers", "get-tool-call-rate", "serve-mcp"):
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
