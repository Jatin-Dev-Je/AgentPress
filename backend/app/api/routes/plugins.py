import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import Agent, AgentPluginConfig, ToolCallAudit
from app.db.session import get_session
from app.plugins.manager import plugin_manager
from app.security.tool_policy import is_tool_allowed

router = APIRouter()

logger = logging.getLogger(__name__)


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
    if settings.tool_calling_mode == "disabled":
        raise HTTPException(status_code=403, detail="tool calling is disabled by configuration")

    if not x_agent_id:
        raise HTTPException(status_code=400, detail="missing x-agent-id header")

    res = await session.execute(select(Agent).where(Agent.id == x_agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")

    if not is_tool_allowed(agent=agent, plugin_id=plugin_id, tool_name=tool_name):
        raise HTTPException(status_code=403, detail="tool call not allowed for this agent")

    agent_id = agent.id
    started_ms = int(time.time() * 1000)
    started_at = datetime.utcnow()
    try:
        res = await session.execute(
            select(AgentPluginConfig).where(
                AgentPluginConfig.agent_id == agent_id,
                AgentPluginConfig.plugin_id == plugin_id,
            )
        )
        cfg = res.scalar_one_or_none()
        plugin_config = cfg.config if cfg else {}

        out = await plugin_manager.call_tool(
            plugin_id=plugin_id,
            tool_name=tool_name,
            params=body.params,
            agent_id=agent_id,
            context_extra={"plugin_config": plugin_config},
        )

        audit = ToolCallAudit(
            agent_id=agent_id,
            conversation_id=None,
            tool_call_id=None,
            plugin_id=plugin_id,
            tool_name=tool_name,
            params=body.params,
            ok=True,
            response=out,
            error=None,
            started_at=started_at,
            ended_at=datetime.utcnow(),
            duration_ms=max(0, int(time.time() * 1000) - started_ms),
        )
        session.add(audit)
        await session.commit()

        return out
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TimeoutError as e:
        audit = ToolCallAudit(
            agent_id=agent_id,
            conversation_id=None,
            tool_call_id=None,
            plugin_id=plugin_id,
            tool_name=tool_name,
            params=body.params,
            ok=False,
            response=None,
            error=str(e),
            started_at=started_at,
            ended_at=datetime.utcnow(),
            duration_ms=max(0, int(time.time() * 1000) - started_ms),
        )
        session.add(audit)
        await session.commit()
        raise HTTPException(status_code=504, detail=str(e))
    except RuntimeError as e:
        logger.exception("Plugin tool call failed: plugin=%s tool=%s agent=%s", plugin_id, tool_name, agent_id)
        detail = str(e).strip()
        if not detail:
            detail = "Plugin tool call failed"

        audit = ToolCallAudit(
            agent_id=agent_id,
            conversation_id=None,
            tool_call_id=None,
            plugin_id=plugin_id,
            tool_name=tool_name,
            params=body.params,
            ok=False,
            response=None,
            error=detail,
            started_at=started_at,
            ended_at=datetime.utcnow(),
            duration_ms=max(0, int(time.time() * 1000) - started_ms),
        )
        session.add(audit)
        await session.commit()
        raise HTTPException(status_code=502, detail=detail)


@router.post("/{plugin_id}/restart")
async def restart_plugin(plugin_id: str) -> dict:
    await plugin_manager.restart_plugin(plugin_id)
    return {"status": "restarted", "plugin_id": plugin_id}
