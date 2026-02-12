from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDirective:
    plugin_id: str
    tool_name: str
    params: dict


def parse_tool_directive(text: str) -> ToolDirective | None:
    """Developer-focused escape hatch until full LLM tool-calling is wired.

    Supported forms:
      - /tool <plugin_id> <tool_name> <json>
        e.g. /tool echo echo {"text": "hi"}

    Returns None if not a tool directive.
    Raises ValueError if directive is malformed.
    """

    stripped = text.strip()
    if not stripped.startswith("/tool "):
        return None

    parts = stripped.split(" ", 3)
    if len(parts) < 4:
        raise ValueError("Tool directive must be: /tool <plugin_id> <tool_name> <json>")

    _, plugin_id, tool_name, json_part = parts
    try:
        params = json.loads(json_part)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON params: {e}") from e

    if not isinstance(params, dict):
        raise ValueError("Tool params must be a JSON object")

    return ToolDirective(plugin_id=plugin_id, tool_name=tool_name, params=params)
