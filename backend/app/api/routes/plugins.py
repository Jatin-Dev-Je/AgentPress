from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Agent
from app.db.session import get_session
from app.plugins.manager import plugin_manager
from app.security.tool_policy import is_tool_allowed

router = APIRouter()


class ToolCallBody(BaseModel):
    params: dict = Field(default_factory=dict)


@router.get("")
async def list_plugins() -> list[dict]:
    return await plugin_manager.list_plugins()


@router.post("/{plugin_id}/tools/{tool_name}")
async def call_tool(
    plugin_id: str,
    tool_name: str,
    body: ToolCallBody,
    x_agent_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not x_agent_id:
        raise HTTPException(status_code=400, detail="missing x-agent-id header")

    res = await session.execute(select(Agent).where(Agent.id == x_agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")

    if not is_tool_allowed(agent=agent, plugin_id=plugin_id, tool_name=tool_name):
        raise HTTPException(status_code=403, detail="tool call not allowed for this agent")

    agent_id = agent.id
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
