from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


class OllamaError(RuntimeError):
    pass


def _format_ollama_http_error(*, status_code: int, body_text: str, model: str) -> str:
    try:
        data = json.loads(body_text)
    except Exception:
        data = None

    error_str = None
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, str):
            error_str = err

    if status_code == 404 and error_str and "model" in error_str and "not found" in error_str:
        return (
            f"Ollama model '{model}' not found. "
            f"Run `ollama pull {model}` or set AGENTPRESS_OLLAMA_MODEL to an installed model. "
            f"(Ollama said: {error_str})"
        )

    if error_str:
        return f"Ollama error {status_code}: {error_str}"

    return f"Ollama error {status_code}: {body_text}"


async def stream_chat(
    *,
    base_url: str,
    model: str,
    messages: list[dict],
    temperature: float | None = None,
    timeout_seconds: float = 60.0,
) -> AsyncIterator[str]:
    """Yield assistant token chunks from Ollama's /api/chat streaming JSONL."""

    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}

    timeout = httpx.Timeout(timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    body_text = body.decode("utf-8", errors="replace")
                    raise OllamaError(
                        _format_ollama_http_error(
                            status_code=resp.status_code,
                            body_text=body_text,
                            model=model,
                        )
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
            raise OllamaError(
                _format_ollama_http_error(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    model=model,
                )
            )

        data = resp.json()
        msg = (data.get("message") or {}).get("content")
        return (msg or "").strip()
