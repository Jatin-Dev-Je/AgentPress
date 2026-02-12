from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.plugins.manager import plugin_manager

router = APIRouter()


class ToolCallBody(BaseModel):
    params: dict = {}


@router.get("")
async def list_plugins() -> list[dict]:
    return await plugin_manager.list_plugins()


@router.post("/{plugin_id}/tools/{tool_name}")
async def call_tool(
    plugin_id: str,
    tool_name: str,
    body: ToolCallBody,
    x_agent_id: str | None = Header(default=None),
) -> dict:
    agent_id = x_agent_id or "dev-agent"
    try:
        return await plugin_manager.call_tool(
            plugin_id=plugin_id,
            tool_name=tool_name,
            params=body.params,
            agent_id=agent_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{plugin_id}/restart")
async def restart_plugin(plugin_id: str) -> dict:
    await plugin_manager.restart_plugin(plugin_id)
    return {"status": "restarted", "plugin_id": plugin_id}
