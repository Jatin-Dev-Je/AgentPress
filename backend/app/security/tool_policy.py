from __future__ import annotations

from app.db.models import Agent


def is_tool_allowed(*, agent: Agent, plugin_id: str, tool_name: str) -> bool:
    """Return True if the agent is allowed to call the tool.

    Policy:
    - If no allowlists are set (both NULL), allow all.
    - If allowed_plugins is set, plugin_id must be in it.
    - If allowed_tools is set, plugin_id must exist as a key and tool_name must be listed.
    """

    allowed_plugins = agent.allowed_plugins
    allowed_tools = agent.allowed_tools

    if allowed_plugins is None and allowed_tools is None:
        return True

    if allowed_plugins is not None and plugin_id not in allowed_plugins:
        return False

    if allowed_tools is not None:
        plugin_tools = allowed_tools.get(plugin_id)
        if not plugin_tools or tool_name not in plugin_tools:
            return False

    return True
