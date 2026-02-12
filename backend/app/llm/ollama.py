from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


class OllamaError(RuntimeError):
    pass


async def stream_chat(
    *,
    base_url: str,
    model: str,
    messages: list[dict],
    timeout_seconds: float = 60.0,
) -> AsyncIterator[str]:
    """Yield assistant token chunks from Ollama's /api/chat streaming JSONL."""

    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    timeout = httpx.Timeout(timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise OllamaError(
                        f"Ollama error {resp.status_code}: {body.decode('utf-8', errors='replace')}"
                    )

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if chunk.get("error"):
                        raise OllamaError(str(chunk["error"]))

                    msg = chunk.get("message") or {}
                    content = msg.get("content")
                    if content:
                        yield content

                    if chunk.get("done") is True:
                        break
        except httpx.RequestError as e:
            raise OllamaError(f"Cannot connect to Ollama at {base_url}: {e}") from e


async def chat_once(
    *,
    base_url: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    timeout_seconds: float = 60.0,
) -> str:
    """Return a single assistant message (non-stream)."""

    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    timeout = httpx.Timeout(timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.RequestError as e:
            raise OllamaError(f"Cannot connect to Ollama at {base_url}: {e}") from e

        if resp.status_code >= 400:
            raise OllamaError(f"Ollama error {resp.status_code}: {resp.text}")

        data = resp.json()
        msg = (data.get("message") or {}).get("content")
        return (msg or "").strip()
