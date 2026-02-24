from __future__ import annotations

from datetime import datetime
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.chat.service import stream_agent_chat
from app.db.models import Agent, AgentPluginConfig, Conversation, Message, ToolCallAudit
from app.db.session import get_session

router = APIRouter()


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="gemini", min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=200)
    system_prompt: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    allowed_plugins: list[str] | None = None
    allowed_tools: dict[str, list[str]] | None = None


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    provider: str | None = Field(default=None, min_length=1, max_length=50)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    allowed_plugins: list[str] | None = None
    allowed_tools: dict[str, list[str]] | None = None


class AgentOut(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    system_prompt: str
    temperature: float
    allowed_plugins: list[str] | None
    allowed_tools: dict[str, list[str]] | None
    created_at: datetime
    updated_at: datetime


def _to_out(a: Agent) -> AgentOut:
    return AgentOut(
        id=a.id,
        name=a.name,
        provider=a.provider,
        model=a.model,
        system_prompt=a.system_prompt,
        temperature=a.temperature,
        allowed_plugins=a.allowed_plugins,
        allowed_tools=a.allowed_tools,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.post("", response_model=AgentOut)
async def create_agent(body: AgentCreate, session: AsyncSession = Depends(get_session)) -> AgentOut:
    agent = Agent(
        name=body.name,
        provider=body.provider,
        model=body.model,
        system_prompt=body.system_prompt,
        temperature=body.temperature,
        allowed_plugins=body.allowed_plugins,
        allowed_tools=body.allowed_tools,
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


class AgentPluginConfigOut(BaseModel):
    agent_id: str
    plugin_id: str
    config: dict


class AgentPluginConfigPut(BaseModel):
    config: dict = Field(default_factory=dict)


class ConversationOut(BaseModel):
    id: str
    agent_id: str
    created_at: datetime
    last_message_at: datetime | None
    last_message_role: str | None
    last_message_excerpt: str | None
    message_count: int


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    token_count: int | None
    seq: int
    created_at: datetime


@router.get("/{agent_id}/plugins/{plugin_id}/config", response_model=AgentPluginConfigOut)
async def get_agent_plugin_config(
    agent_id: str,
    plugin_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentPluginConfigOut:
    # Ensure agent exists.
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    res = await session.execute(
        select(AgentPluginConfig).where(
            AgentPluginConfig.agent_id == agent_id,
            AgentPluginConfig.plugin_id == plugin_id,
        )
    )
    row = res.scalar_one_or_none()
    return AgentPluginConfigOut(agent_id=agent_id, plugin_id=plugin_id, config=(row.config if row else {}))


@router.put("/{agent_id}/plugins/{plugin_id}/config", response_model=AgentPluginConfigOut)
async def put_agent_plugin_config(
    agent_id: str,
    plugin_id: str,
    body: AgentPluginConfigPut,
    session: AsyncSession = Depends(get_session),
) -> AgentPluginConfigOut:
    # Ensure agent exists.
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    res = await session.execute(
        select(AgentPluginConfig).where(
            AgentPluginConfig.agent_id == agent_id,
            AgentPluginConfig.plugin_id == plugin_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = AgentPluginConfig(agent_id=agent.id, plugin_id=plugin_id, config=body.config)
        session.add(row)
    else:
        row.config = body.config

    await session.commit()
    await session.refresh(row)

    return AgentPluginConfigOut(agent_id=row.agent_id, plugin_id=row.plugin_id, config=row.config)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, body: AgentUpdate, session: AsyncSession = Depends(get_session)) -> AgentOut:
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.provider is not None:
        agent.provider = body.provider
    if body.model is not None:
        agent.model = body.model
    if body.system_prompt is not None:
        agent.system_prompt = body.system_prompt
    if body.temperature is not None:
        agent.temperature = body.temperature

    # Allow explicit clearing by sending null (None) by checking fields_set.
    if "allowed_plugins" in body.model_fields_set:
        agent.allowed_plugins = body.allowed_plugins
    if "allowed_tools" in body.model_fields_set:
        agent.allowed_tools = body.allowed_tools

    await session.commit()
    await session.refresh(agent)
    return _to_out(agent)


@router.get("/{agent_id}/conversations", response_model=list[ConversationOut])
async def list_agent_conversations(agent_id: str, session: AsyncSession = Depends(get_session)) -> list[ConversationOut]:
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    stats = (
        select(
            Message.conversation_id.label("cid"),
            func.max(Message.created_at).label("last_at"),
            func.count(Message.id).label("message_count"),
            func.max(Message.seq).label("last_seq"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    last_msg = aliased(Message)

    q = (
        select(
            Conversation,
            stats.c.last_at,
            stats.c.message_count,
            last_msg.role,
            last_msg.content,
        )
        .where(Conversation.agent_id == agent_id)
        .outerjoin(stats, stats.c.cid == Conversation.id)
        .outerjoin(
            last_msg,
            (last_msg.conversation_id == Conversation.id) & (last_msg.seq == stats.c.last_seq),
        )
        .order_by(Conversation.created_at.desc())
    )

    res = await session.execute(q)
    out: list[ConversationOut] = []
    for conv, last_at, message_count, last_role, last_content in res.all():
        excerpt = None
        if isinstance(last_content, str) and last_content:
            excerpt = (last_content[:140] + "…") if len(last_content) > 140 else last_content

        out.append(
            ConversationOut(
                id=conv.id,
                agent_id=conv.agent_id,
                created_at=conv.created_at,
                last_message_at=last_at,
                last_message_role=last_role,
                last_message_excerpt=excerpt,
                message_count=int(message_count or 0),
            )
        )
    return out


@router.get("/{agent_id}/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_conversation_messages(
    agent_id: str,
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    res = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.agent_id == agent_id,
        )
    )
    conv = res.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    res = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.seq.asc(), Message.created_at.asc())
    )
    msgs = list(res.scalars().all())
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            token_count=m.token_count,
            seq=m.seq,
            created_at=m.created_at,
        )
        for m in msgs
    ]


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Defensive explicit deletes to keep behavior consistent even when the DB
    # doesn't enforce FK cascades (e.g., SQLite without foreign_keys pragma).
    await session.execute(delete(ToolCallAudit).where(ToolCallAudit.agent_id == agent_id))
    await session.execute(delete(AgentPluginConfig).where(AgentPluginConfig.agent_id == agent_id))
    await session.execute(delete(Conversation).where(Conversation.agent_id == agent_id))
    await session.execute(delete(Agent).where(Agent.id == agent_id))

    await session.commit()
    return {"ok": True}


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
        except asyncio.CancelledError:
            raise
        except KeyError as e:
            if str(e).strip("'") == "agent_not_found":
                yield b"event: error\ndata: {\"code\":\"not_found\",\"message\":\"Agent not found\"}\n\n"
            elif str(e).strip("'") == "conversation_not_found":
                yield b"event: error\ndata: {\"code\":\"not_found\",\"message\":\"Conversation not found\"}\n\n"
            else:
                yield b"event: error\ndata: {\"code\":\"error\",\"message\":\"Unknown error\"}\n\n"
        except ValueError as e:
            msg = str(e).replace('"', "\\\"")
            yield f'event: error\ndata: {{"code":"bad_request","message":"{msg}"}}\n\n'.encode("utf-8")
        except Exception as e:
            msg = str(e).replace('"', "\\\"")
            yield f'event: error\ndata: {{"code":"error","message":"{msg}"}}\n\n'.encode("utf-8")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
