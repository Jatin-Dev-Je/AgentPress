from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import list_auth_failures
from app.plugins.manager import plugin_manager

router = APIRouter()


@router.get("/auth-failures")
async def get_auth_failures(limit: int = Query(default=200, ge=1, le=2000)) -> dict:
    return {"events": list_auth_failures(limit=limit)}


@router.get("/tool-calls")
async def get_tool_call_audit(limit: int = Query(default=200, ge=1, le=2000)) -> dict:
    return {"events": plugin_manager.list_tool_call_audit(limit=limit)}
