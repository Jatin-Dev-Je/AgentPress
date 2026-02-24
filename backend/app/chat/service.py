from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.sse import sse
from app.chat.auto_tools import build_react_system_prompt, build_tools_prompt_fragment, try_parse_tool_call
from app.chat.tool_directive import parse_tool_directive
from app.core.settings import settings
from app.db.models import Agent, AgentPluginConfig, Conversation, Message, ToolCall, ToolCallAudit
from app.llm.gemini import GeminiError
from app.llm.ollama import OllamaError
from app.llm import gemini as gemini_llm
from app.llm import ollama as ollama_llm
from app.plugins.manager import plugin_manager
from app.security.tool_policy import is_tool_allowed


def _approx_token_count(text: str) -> int:
    # Lightweight approximation (does not require a tokenizer dependency).
    # Good enough for basic analytics; can be replaced with provider-specific tokenization later.
    return len((text or "").split())


def _resolve_agent_llm(agent: Agent) -> tuple[str, str]:
    """Return (provider, model) for runtime use.

    Back-compat:
    - Older UI stored provider-like values in Agent.model (e.g. "ollama").
    - In that case, fall back to configured default model.
    """

    provider = (getattr(agent, "provider", None) or settings.llm_provider or "gemini").strip() or "gemini"
    model = (agent.model or "").strip()

    if provider == "ollama" and model.lower() in {"ollama", "openai", "anthropic"}:
        model = (settings.ollama_model or "").strip()
    if provider == "ollama" and not model:
        model = (settings.ollama_model or "").strip()

    if provider == "gemini" and not model:
        model = (settings.gemini_model or "").strip()

    return provider, model


async def _chat_once(*, provider: str, model: str, messages: list[dict], temperature: float) -> str:
    if provider == "ollama":
        return await ollama_llm.chat_once(
            base_url=settings.ollama_base_url,
            model=model,
            messages=messages,
            temperature=temperature,
        )
    if provider == "gemini":
        try:
            return await gemini_llm.chat_once(
                api_key=settings.gemini_api_key or "",
                base_url=settings.gemini_base_url,
                model=model,
                messages=messages,
                temperature=temperature,
            )
        except GeminiError as e:
            if e.is_rate_limited():
                fallback_model = (settings.ollama_model or "").strip() or "llama3.2:1b"
                return await ollama_llm.chat_once(
                    base_url=settings.ollama_base_url,
                    model=fallback_model,
                    messages=messages,
                    temperature=temperature,
                )
            raise
    raise ValueError(f"unsupported provider: {provider}")


def _stream_chat(*, provider: str, model: str, messages: list[dict], temperature: float) -> AsyncIterator[str]:
    if provider == "ollama":
        return ollama_llm.stream_chat(
            base_url=settings.ollama_base_url,
            model=model,
            messages=messages,
            temperature=temperature,
        )
    if provider == "gemini":
        async def _gen() -> AsyncIterator[str]:
            yielded_any = False
            try:
                async for t in gemini_llm.stream_chat(
                    api_key=settings.gemini_api_key or "",
                    base_url=settings.gemini_base_url,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                ):
                    yielded_any = True
                    yield t
            except GeminiError as e:
                if (not yielded_any) and e.is_rate_limited():
                    fallback_model = (settings.ollama_model or "").strip() or "llama3.2:1b"
                    async for t in ollama_llm.stream_chat(
                        base_url=settings.ollama_base_url,
                        model=fallback_model,
                        messages=messages,
                        temperature=temperature,
                    ):
                        yield t
                    return
                raise

        return _gen()
    raise ValueError(f"unsupported provider: {provider}")


async def _get_agent_plugin_config(session: AsyncSession, *, agent_id: str, plugin_id: str) -> dict:
    res = await session.execute(
        select(AgentPluginConfig).where(
            AgentPluginConfig.agent_id == agent_id,
            AgentPluginConfig.plugin_id == plugin_id,
        )
    )
    row = res.scalar_one_or_none()
    return row.config if row else {}


async def stream_agent_chat(
    *,
    session: AsyncSession,
    agent_id: str,
    user_text: str,
    conversation_id: str | None,
) -> AsyncIterator[bytes]:
    agent = await _get_agent(session, agent_id)

    conversation = await _get_or_create_conversation(session, agent_id, conversation_id)

    next_seq = await _next_seq(session, conversation.id)
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_text,
        token_count=_approx_token_count(user_text),
        seq=next_seq,
    )
    session.add(user_msg)
    await session.commit()
    await session.refresh(user_msg)

    yield sse("conversation", {"conversation_id": conversation.id})
    yield sse("message_start", {"role": "assistant"})

    history = await _load_messages(session, conversation.id)
    base_messages: list[dict] = []
    for m in history:
        if m.role in ("user", "assistant"):
            base_messages.append({"role": m.role, "content": m.content})

    assistant_text_parts: list[str] = []

    # MVP tool visibility: allow explicit tool invocation via /tool directive.
    if settings.tool_calling_mode == "disabled" and user_text.strip().startswith("/tool "):
        yield sse(
            "tool_call_error",
            {
                "tool_id": None,
                "plugin": None,
                "tool_name": None,
                "error": "Tool calling is disabled by configuration",
            },
        )
        return

    try:
        directive = parse_tool_directive(user_text)
    except ValueError as e:
        yield sse(
            "tool_call_error",
            {
                "tool_id": None,
                "plugin": None,
                "tool_name": None,
                "error": str(e),
            },
        )
        return
    if directive is not None:
        if settings.tool_calling_mode not in ("manual", "auto"):
            yield sse(
                "tool_call_error",
                {
                    "tool_id": None,
                    "plugin": directive.plugin_id,
                    "tool_name": directive.tool_name,
                    "error": f"Invalid tool_calling_mode: {settings.tool_calling_mode}",
                },
            )
            return

        if not is_tool_allowed(agent=agent, plugin_id=directive.plugin_id, tool_name=directive.tool_name):
            yield sse(
                "tool_call_error",
                {
                    "tool_id": None,
                    "plugin": directive.plugin_id,
                    "tool_name": directive.tool_name,
                    "error": "Tool call blocked by agent allowlist policy",
                },
            )
            return

        tool_call = ToolCall(
            conversation_id=conversation.id,
            plugin_id=directive.plugin_id,
            tool_name=directive.tool_name,
            params=directive.params,
            status="running",
        )
        session.add(tool_call)
        await session.commit()
        await session.refresh(tool_call)

        started_ms = int(time.time() * 1000)
        started_at = datetime.utcnow()
        yield sse(
            "tool_call_start",
            {
                "tool_id": tool_call.id,
                "plugin": directive.plugin_id,
                "tool_name": directive.tool_name,
                "params": directive.params,
            },
        )

        try:
            out = await plugin_manager.call_tool(
                plugin_id=directive.plugin_id,
                tool_name=directive.tool_name,
                params=directive.params,
                agent_id=agent_id,
                context_extra={
                    "plugin_config": await _get_agent_plugin_config(
                        session,
                        agent_id=agent_id,
                        plugin_id=directive.plugin_id,
                    )
                },
            )
            tool_call.status = "completed"
            tool_call.result = out
            tool_call.duration_ms = int(time.time() * 1000) - started_ms
            tool_call.ended_at = datetime.utcnow()

            session.add(
                ToolCallAudit(
                    agent_id=agent_id,
                    conversation_id=conversation.id,
                    tool_call_id=tool_call.id,
                    plugin_id=directive.plugin_id,
                    tool_name=directive.tool_name,
                    params=directive.params,
                    ok=True,
                    response=out,
                    error=None,
                    started_at=started_at,
                    ended_at=tool_call.ended_at,
                    duration_ms=tool_call.duration_ms,
                )
            )
            await session.commit()

            yield sse(
                "tool_call_end",
                {
                    "tool_id": tool_call.id,
                    "success": True,
                    "result": out,
                    "duration_ms": tool_call.duration_ms,
                },
            )

            assistant_text = json.dumps(out, indent=2)
            assistant_text_parts.append(assistant_text)
            yield sse("token", {"text": assistant_text})
        except Exception as e:
            tool_call.status = "failed"
            tool_call.error = str(e)
            tool_call.duration_ms = int(time.time() * 1000) - started_ms
            tool_call.ended_at = datetime.utcnow()

            session.add(
                ToolCallAudit(
                    agent_id=agent_id,
                    conversation_id=conversation.id,
                    tool_call_id=tool_call.id,
                    plugin_id=directive.plugin_id,
                    tool_name=directive.tool_name,
                    params=directive.params,
                    ok=False,
                    response=None,
                    error=str(e),
                    started_at=started_at,
                    ended_at=tool_call.ended_at,
                    duration_ms=tool_call.duration_ms,
                )
            )
            await session.commit()

            yield sse(
                "tool_call_error",
                {
                    "tool_id": tool_call.id,
                    "plugin": directive.plugin_id,
                    "tool_name": directive.tool_name,
                    "error": str(e),
                    "duration_ms": tool_call.duration_ms,
                },
            )
            return

        assistant_text = "".join(assistant_text_parts).strip()
        next_seq = await _next_seq(session, conversation.id)
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_text,
            token_count=_approx_token_count(assistant_text),
            seq=next_seq,
        )
        session.add(assistant_msg)
        await session.commit()
        await session.refresh(assistant_msg)

        yield sse(
            "message_end",
            {
                "conversation_id": conversation.id,
                "message_id": assistant_msg.id,
                "duration_ms": int(time.time() * 1000) - started_ms,
            },
        )
        return

    if settings.tool_calling_mode == "auto":
        provider, model = _resolve_agent_llm(agent)

        tools_fragment = await build_tools_prompt_fragment(
            allowed_plugins=agent.allowed_plugins,
            allowed_tools=agent.allowed_tools,
        )
        system_prompt = build_react_system_prompt(
            base_system_prompt=agent.system_prompt or "",
            tools_fragment=tools_fragment,
        )
        ollama_messages: list[dict] = [{"role": "system", "content": system_prompt}, *base_messages]

        started_ms = int(time.time() * 1000)
        max_tool_calls = 5
        tool_calls_used = 0
        seen_signatures: dict[str, int] = {}

        while True:
            try:
                assistant_reply = await _chat_once(
                    provider=provider,
                    model=model,
                    messages=ollama_messages,
                    temperature=agent.temperature,
                )
            except OllamaError as e:
                yield sse("error", {"code": "ollama_error", "message": str(e)})
                return
            except GeminiError as e:
                yield sse("error", {"code": "gemini_error", "message": str(e)})
                return
            except ValueError as e:
                yield sse("error", {"code": "unsupported_provider", "message": str(e)})
                return

            payload = try_parse_tool_call(assistant_reply)
            if payload is None:
                final_text = assistant_reply.strip()
                if final_text:
                    assistant_text_parts.append(final_text)
                    # Emit as chunks to avoid huge single SSE payloads.
                    chunk_size = 1200
                    for i in range(0, len(final_text), chunk_size):
                        yield sse("token", {"text": final_text[i : i + chunk_size]})
                break

            if tool_calls_used >= max_tool_calls:
                yield sse(
                    "error",
                    {
                        "code": "tool_call_limit",
                        "message": f"Exceeded max tool calls ({max_tool_calls}) in auto mode",
                    },
                )
                return

            plugin_id = payload.get("plugin_id")
            tool_name = payload.get("tool_name")
            params = payload.get("params")
            if not isinstance(plugin_id, str) or not isinstance(tool_name, str) or not isinstance(params, dict):
                yield sse(
                    "error",
                    {
                        "code": "invalid_tool_call",
                        "message": "Invalid TOOL_CALL payload; expected plugin_id/tool_name strings and params object",
                        "raw": payload,
                    },
                )
                return

            if not is_tool_allowed(agent=agent, plugin_id=plugin_id, tool_name=tool_name):
                yield sse(
                    "error",
                    {
                        "code": "tool_not_allowed",
                        "message": "Tool call blocked by agent allowlist policy",
                        "plugin_id": plugin_id,
                        "tool_name": tool_name,
                    },
                )
                return

            signature = f"{plugin_id}::{tool_name}::{json.dumps(params, sort_keys=True, separators=(',', ':'))}"
            seen_signatures[signature] = seen_signatures.get(signature, 0) + 1
            if seen_signatures[signature] >= 3:
                yield sse(
                    "error",
                    {
                        "code": "tool_call_loop",
                        "message": "Detected repeated identical tool calls; stopping to avoid a loop",
                        "plugin_id": plugin_id,
                        "tool_name": tool_name,
                        "params": params,
                    },
                )
                return

            tool_calls_used += 1

            tool_call = ToolCall(
                conversation_id=conversation.id,
                plugin_id=plugin_id,
                tool_name=tool_name,
                params=params,
                status="running",
            )
            session.add(tool_call)
            await session.commit()
            await session.refresh(tool_call)

            call_started_ms = int(time.time() * 1000)
            call_started_at = datetime.utcnow()
            yield sse(
                "tool_call_start",
                {
                    "tool_id": tool_call.id,
                    "plugin": plugin_id,
                    "tool_name": tool_name,
                    "params": params,
                },
            )

            # Record what the model asked for, then provide the result back in-band.
            ollama_messages.append({"role": "assistant", "content": assistant_reply})

            try:
                out = await plugin_manager.call_tool(
                    plugin_id=plugin_id,
                    tool_name=tool_name,
                    params=params,
                    agent_id=agent_id,
                    context_extra={
                        "plugin_config": await _get_agent_plugin_config(
                            session,
                            agent_id=agent_id,
                            plugin_id=plugin_id,
                        )
                    },
                )
                tool_call.status = "completed"
                tool_call.result = out
                tool_call.duration_ms = int(time.time() * 1000) - call_started_ms
                tool_call.ended_at = datetime.utcnow()

                session.add(
                    ToolCallAudit(
                        agent_id=agent_id,
                        conversation_id=conversation.id,
                        tool_call_id=tool_call.id,
                        plugin_id=plugin_id,
                        tool_name=tool_name,
                        params=params,
                        ok=True,
                        response=out,
                        error=None,
                        started_at=call_started_at,
                        ended_at=tool_call.ended_at,
                        duration_ms=tool_call.duration_ms,
                    )
                )
                await session.commit()

                yield sse(
                    "tool_call_end",
                    {
                        "tool_id": tool_call.id,
                        "success": True,
                        "result": out,
                        "duration_ms": tool_call.duration_ms,
                    },
                )

                ollama_messages.append(
                    {
                        "role": "user",
                        "content": "TOOL_RESULT " + json.dumps(out, ensure_ascii=False),
                    }
                )
                ollama_messages.append(
                    {
                        "role": "user",
                        "content": "Now provide the final answer to the user. "
                        "If you have enough information, do NOT call any more tools.",
                    }
                )
            except Exception as e:
                tool_call.status = "failed"
                tool_call.error = str(e)
                tool_call.duration_ms = int(time.time() * 1000) - call_started_ms
                tool_call.ended_at = datetime.utcnow()

                session.add(
                    ToolCallAudit(
                        agent_id=agent_id,
                        conversation_id=conversation.id,
                        tool_call_id=tool_call.id,
                        plugin_id=plugin_id,
                        tool_name=tool_name,
                        params=params,
                        ok=False,
                        response=None,
                        error=str(e),
                        started_at=call_started_at,
                        ended_at=tool_call.ended_at,
                        duration_ms=tool_call.duration_ms,
                    )
                )
                await session.commit()

                yield sse(
                    "tool_call_error",
                    {
                        "tool_id": tool_call.id,
                        "plugin": plugin_id,
                        "tool_name": tool_name,
                        "error": str(e),
                        "duration_ms": tool_call.duration_ms,
                    },
                )
                return

        assistant_text = "".join(assistant_text_parts).strip()
        next_seq = await _next_seq(session, conversation.id)
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_text,
            token_count=_approx_token_count(assistant_text),
            seq=next_seq,
        )
        session.add(assistant_msg)
        await session.commit()
        await session.refresh(assistant_msg)

        yield sse(
            "message_end",
            {
                "conversation_id": conversation.id,
                "message_id": assistant_msg.id,
                "duration_ms": int(time.time() * 1000) - started_ms,
            },
        )
        return

    provider, model = _resolve_agent_llm(agent)

    ollama_messages: list[dict] = []
    if agent.system_prompt:
        ollama_messages.append({"role": "system", "content": agent.system_prompt})
    ollama_messages.extend(base_messages)

    started_ms = int(time.time() * 1000)
    try:
        async for token in _stream_chat(
            provider=provider,
            model=model,
            messages=ollama_messages,
            temperature=agent.temperature,
        ):
            assistant_text_parts.append(token)
            yield sse("token", {"text": token})
    except OllamaError as e:
        yield sse("error", {"code": "ollama_error", "message": str(e)})
        return
    except GeminiError as e:
        yield sse("error", {"code": "gemini_error", "message": str(e)})
        return
    except ValueError as e:
        yield sse("error", {"code": "unsupported_provider", "message": str(e)})
        return

    assistant_text = "".join(assistant_text_parts).strip()
    next_seq = await _next_seq(session, conversation.id)
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_text,
        token_count=_approx_token_count(assistant_text),
        seq=next_seq,
    )
    session.add(assistant_msg)
    await session.commit()
    await session.refresh(assistant_msg)

    yield sse(
        "message_end",
        {
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "duration_ms": int(time.time() * 1000) - started_ms,
        },
    )


async def _get_agent(session: AsyncSession, agent_id: str) -> Agent:
    res = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise KeyError("agent_not_found")
    return agent


async def _get_or_create_conversation(
    session: AsyncSession, agent_id: str, conversation_id: str | None
) -> Conversation:
    if conversation_id:
        res = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.agent_id == agent_id)
        )
        convo = res.scalar_one_or_none()
        if convo is None:
            raise KeyError("conversation_not_found")
        return convo

    convo = Conversation(agent_id=agent_id)
    session.add(convo)
    await session.commit()
    await session.refresh(convo)
    return convo


async def _load_messages(session: AsyncSession, conversation_id: str) -> list[Message]:
    res = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.seq.asc())
    )
    return list(res.scalars().all())


async def _next_seq(session: AsyncSession, conversation_id: str) -> int:
    res = await session.execute(select(func.max(Message.seq)).where(Message.conversation_id == conversation_id))
    max_seq = res.scalar_one_or_none()
    return int(max_seq or 0) + 1
