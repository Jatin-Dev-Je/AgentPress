from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ToolCallAudit
from app.db.session import get_session

router = APIRouter()


@router.get("/tool-calls")
async def get_tool_call_audit(
    limit: int = Query(default=200, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(
        select(ToolCallAudit).order_by(ToolCallAudit.created_at.desc()).limit(limit)
    )
    rows = list(res.scalars().all())
    return {
        "events": [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "conversation_id": r.conversation_id,
                "tool_call_id": r.tool_call_id,
                "plugin_id": r.plugin_id,
                "tool_name": r.tool_name,
                "params": r.params,
                "ok": r.ok,
                "response": r.response,
                "error": r.error,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
