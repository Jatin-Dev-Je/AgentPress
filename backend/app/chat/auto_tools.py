from __future__ import annotations

import json

from app.plugins.manager import plugin_manager


def try_parse_tool_call(text: str) -> dict | None:
    """Parse a tool call marker emitted by the model.

    We *prefer* the strict format:
      TOOL_CALL {json}

    In practice, some models add extra whitespace or wrapper text.
    This parser finds the first occurrence of 'TOOL_CALL' and then extracts the
    first balanced JSON object that follows it.

    Returns payload dict or None.
    Expected shape (validated later in the caller):
      {"plugin_id": "...", "tool_name": "...", "params": {...}}
    """

    marker = "TOOL_CALL"
    idx = text.find(marker)
    if idx < 0:
        return None

    after = text[idx + len(marker) :]
    json_s = _extract_first_json_object(after)
    if not json_s:
        return None

    try:
        payload = json.loads(json_s)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


async def build_tools_prompt_fragment(
    *,
    allowed_plugins: list[str] | None = None,
    allowed_tools: dict[str, list[str]] | None = None,
) -> str:
    """Compact tool catalog for ReAct-style prompting.

    v1: includes all installed plugin tools.
    Later: filter by agent-enabled plugins/tools.
    """

    plugins = await plugin_manager.list_plugins()

    if allowed_plugins is not None:
        plugins = [p for p in plugins if p.get("id") in set(allowed_plugins)]

    if allowed_tools is not None:
        filtered: list[dict] = []
        for p in plugins:
            pid = p.get("id")
            if not isinstance(pid, str):
                continue
            allowed = allowed_tools.get(pid) or []
            tools = p.get("tools") or []
            if allowed:
                tools = [t for t in tools if t.get("name") in set(allowed)]
            else:
                tools = []
            p2 = dict(p)
            p2["tools"] = tools
            filtered.append(p2)
        plugins = filtered

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
