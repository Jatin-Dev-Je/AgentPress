from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.service import stream_agent_chat
from app.db.models import Agent
from app.db.session import get_session

router = APIRouter()


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    system_prompt: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class AgentOut(BaseModel):
    id: str
    name: str
    model: str
    system_prompt: str
    temperature: float
    created_at: datetime
    updated_at: datetime


def _to_out(a: Agent) -> AgentOut:
    return AgentOut(
        id=a.id,
        name=a.name,
        model=a.model,
        system_prompt=a.system_prompt,
        temperature=a.temperature,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.post("", response_model=AgentOut)
async def create_agent(body: AgentCreate, session: AsyncSession = Depends(get_session)) -> AgentOut:
    agent = Agent(
        name=body.name,
        model=body.model,
        system_prompt=body.system_prompt,
        temperature=body.temperature,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return _to_out(agent)


@router.get("", response_model=list[AgentOut])
async def list_agents(session: AsyncSession = Depends(get_session)) -> list[AgentOut]:
    res = await session.execute(select(Agent).order_by(Agent.created_at.desc()))
    agents = list(res.scalars().all())
    return [_to_out(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)) -> AgentOut:
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _to_out(agent)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, body: AgentUpdate, session: AsyncSession = Depends(get_session)) -> AgentOut:
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.model is not None:
        agent.model = body.model
    if body.system_prompt is not None:
        agent.system_prompt = body.system_prompt
    if body.temperature is not None:
        agent.temperature = body.temperature

    await session.commit()
    await session.refresh(agent)
    return _to_out(agent)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


@router.post("/{agent_id}/chat")
async def chat_agent(agent_id: str, body: ChatRequest, session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    async def gen():
        try:
            async for chunk in stream_agent_chat(
                session=session,
                agent_id=agent_id,
                user_text=body.message,
                conversation_id=body.conversation_id,
            ):
                yield chunk
        except KeyError as e:
            if str(e).strip("'") == "agent_not_found":
                yield b"event: error\ndata: {\"code\":\"not_found\",\"message\":\"Agent not found\"}\n\n"
            elif str(e).strip("'") == "conversation_not_found":
                yield b"event: error\ndata: {\"code\":\"not_found\",\"message\":\"Conversation not found\"}\n\n"
            else:
                yield b"event: error\ndata: {\"code\":\"error\",\"message\":\"Unknown error\"}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
