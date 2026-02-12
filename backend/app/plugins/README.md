Plugin runtime notes:

- v1 transport: MCP over stdio (JSON-RPC 2.0, newline-delimited)
- Default process model: one process per plugin (shared across agents)
- Override: set `isolation` to `per-agent` in plugin.json to start one process per agent
