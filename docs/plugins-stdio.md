# MCP plugins over stdio (Agentpress v1)

Agentpress runs plugins as subprocesses and communicates over **JSON-RPC 2.0** via **stdin/stdout** (one JSON message per line).

## Required methods (v1)

### `initialize`
- Request: `{ "jsonrpc": "2.0", "id": "...", "method": "initialize", "params": { ... } }`
- Response: `{ "jsonrpc": "2.0", "id": "...", "result": { ... } }`

### `tools/list`
- Response result must include:
  - `tools`: array of `{ name, description, inputSchema }`

### `tools/call`
- Request params:
  - `name`: tool name
  - `arguments`: object
  - `context`: object (Agentpress always includes `agent_id`)

## Manifest
Each plugin folder contains a `plugin.json`:
- `id` (folder name)
- `entrypoint` (default `main.py`)
- `mcp.transport`: must be `"stdio"` for v1
- `isolation`: `"shared"` (default) or `"per-agent"`

## Example
See `plugins/installed/echo`.
