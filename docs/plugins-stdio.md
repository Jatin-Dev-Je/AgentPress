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

## Per-agent plugin config (`plugin_config`)

Agentpress supports storing per-agent plugin configuration in the database and injecting it into every tool call as `context.plugin_config`.

### Set / Get config (HTTP API)

- Set config:
  - `PUT /agents/{agent_id}/plugins/{plugin_id}/config`
  - JSON body: `{ "config": { ... } }`
- Get config:
  - `GET /agents/{agent_id}/plugins/{plugin_id}/config`

### Call a tool (HTTP API)

- `POST /plugins/{plugin_id}/tools/{tool_name}`
- Required header: `X-Agent-Id: {agent_id}`
- JSON body: `{ "params": { ... } }`

### Example configs for v0.1 launch plugins

These examples match the plugins shipped under `plugins/installed/*`.

#### `file-summarize`

Required config:

```json
{
  "base_dir": "D:/AgentPress",
  "max_bytes": 200000,
  "allowed_extensions": [".md", ".txt", ".json"],
  "deny_patterns": ["..", "~"]
}
```

Tool example (list directory):

```json
{ "params": { "path": "", "recursive": false, "limit": 20 } }
```

#### `github-issues`

Optional config (works without token for public repos; token increases rate limits and allows private repos):

```json
{
  "token": "<github_pat_redacted>",
  "default_repo": "octocat/Hello-World",
  "api_base": "https://api.github.com",
  "max_items": 50
}
```

Tool examples:

```json
{ "params": { "state": "open", "limit": 10 } }
```

```json
{ "params": { "number": 1234 } }
```

#### `postgres-query`

Required config:

```json
{
  "dsn": "postgresql://user:password@localhost:5432/dbname",
  "max_rows": 200,
  "timeout_seconds": 10,
  "statement_timeout_ms": 10000
}
```

Tool example:

```json
{ "params": { "sql": "select 1 as one" } }
```

Notes:
- The plugin enforces read-only queries (WITH/SELECT/SHOW/EXPLAIN) and blocks multi-statement SQL.
- Strongly prefer using a DB user/role that is read-only at the database level as a defense-in-depth measure.

## Example
See `plugins/installed/echo`.
