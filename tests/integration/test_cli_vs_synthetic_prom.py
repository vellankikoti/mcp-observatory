from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


def _pick_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Handler(BaseHTTPRequestHandler):
    CANNED = {
        "result": [
            {"metric": {"service": "s1"}, "value": [0, "1"]},
            {"metric": {"service": "s2"}, "value": [0, "1"]},
        ]
    }

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps({"status": "success", "data": self.CANNED}).encode()
        self.wfile.write(body)

    def log_message(self, *a, **kw):
        pass


@pytest.fixture()
def synthetic_prom():
    port = _pick_port()
    server = HTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.mark.integration
def test_cli_list_mcp_servers(synthetic_prom):
    result = subprocess.run(
        [sys.executable, "-m", "observatory.cli", "list-mcp-servers",
         "--prom-url", synthetic_prom, "--format", "json"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    data = json.loads(result.stdout)
    assert data == ["s1", "s2"]
