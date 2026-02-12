from __future__ import annotations

import json
import re

from app.plugins.manager import plugin_manager

_TOOL_CALL_RE = re.compile(r"^TOOL_CALL\s+(\{.*\})\s*$", re.DOTALL)


def try_parse_tool_call(text: str) -> dict | None:
    """Parse a strict tool-call line: `TOOL_CALL {json}`.

    Returns payload dict or None.
    Expected shape:
      {"plugin_id": "...", "tool_name": "...", "params": {...}}
    """

    m = _TOOL_CALL_RE.match(text.strip())
    if not m:
        return None

    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return payload


async def build_tools_prompt_fragment() -> str:
    """Compact tool catalog for ReAct-style prompting.

    v1: includes all installed plugin tools.
    Later: filter by agent-enabled plugins/tools.
    """

    plugins = await plugin_manager.list_plugins()

    lines: list[str] = ["Available tools (MCP plugins):"]

    has_any = False
    for p in plugins:
        plugin_id = p.get("id")
        tools = p.get("tools") or []
        if not tools:
            continue

        has_any = True
        lines.append(f"- plugin: {plugin_id}")
        for t in tools:
            name = t.get("name")
            desc = t.get("description") or ""
            schema = t.get("inputSchema") or {}
            schema_s = json.dumps(schema, ensure_ascii=False)
            lines.append(f"  - {name}: {desc}")
            lines.append(f"    inputSchema: {schema_s}")

    if not has_any:
        lines.append("(none installed)")

    return "\n".join(lines)


def build_react_system_prompt(*, base_system_prompt: str, tools_fragment: str) -> str:
    protocol = (
        "You may call tools to perform actions. "
        "If you need a tool, respond with EXACTLY one line and nothing else:\n"
        "TOOL_CALL {\"plugin_id\":\"...\",\"tool_name\":\"...\",\"params\":{...}}\n\n"
        "If you do NOT need a tool, respond normally with helpful text. "
        "Never include TOOL_CALL in normal text."
    )

    parts = [base_system_prompt.strip(), tools_fragment.strip(), protocol]
    return "\n\n".join([p for p in parts if p]).strip()
