# mcp-observatory-server

MCP query-router + CLI for observing distributed MCP server fleets. 9 typed query tools including the hero `detect_tool_abandonment` signal.

## Install

```bash
uvx mcp-observatory-server --help
# or
pip install mcp-observatory-server
```

## Claude Desktop

```json
{
  "mcpServers": {
    "observatory": {
      "command": "uvx",
      "args": ["mcp-observatory-server", "serve-mcp"]
    }
  }
}
```

## Tools

`list_mcp_servers`, `get_tool_call_rate`, `get_tool_error_rate`, `get_tool_latency_p99`, `compare_servers`, `detect_tool_abandonment`, `get_fleet_health`, `explain_fleet_health`, `verify_services`.

See the [main repo](https://github.com/vellankikoti/mcp-observatory) for design, workshop, Helm chart, and SDK docs.

Companion: [**mcp-observatory-sdk**](https://pypi.org/project/mcp-observatory-sdk/) — instrument your MCP servers to emit the metrics this tool consumes.
