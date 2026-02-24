from __future__ import annotations

import json
from collections.abc import AsyncIterator
import logging
import subprocess

import httpx


logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    pass


def _is_model_not_found(*, status_code: int, body_text: str) -> bool:
    if status_code != 404:
        return False
    try:
        data = json.loads(body_text)
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    err = data.get("error")
    if not isinstance(err, str):
        return False
    s = err.lower()
    return "model" in s and "not found" in s


def _get_installed_ollama_models(timeout_seconds: float = 2.5) -> list[str]:
    """Best-effort local discovery of installed models via the `ollama` CLI."""

    try:
        cp = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception:
        return []

    out = (cp.stdout or "").splitlines()
    models: list[str] = []
    for line in out:
        s = line.strip()
        if not s or s.lower().startswith("name"):
            continue
        # Table format: NAME  ID  SIZE  MODIFIED
        parts = s.split()
        if parts:
            models.append(parts[0])
    return models


def _pick_fallback_model(*, exclude: str) -> str | None:
    models = _get_installed_ollama_models()
    for m in models:
        if m != exclude:
            return m
    return None


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
        attempt_models: list[str] = [model]
        fallback = None
        if model:
            fallback = _pick_fallback_model(exclude=model)
        if fallback:
            attempt_models.append(fallback)

        last_err: OllamaError | None = None
        for attempt_model in attempt_models:
            payload["model"] = attempt_model
            try:
                async with client.stream("POST", url, json=payload) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        body_text = body.decode("utf-8", errors="replace")
                        if attempt_model == model and _is_model_not_found(status_code=resp.status_code, body_text=body_text) and fallback:
                            logger.warning(
                                "Ollama model '%s' not found; falling back to installed model '%s'",
                                model,
                                fallback,
                            )
                            continue
                        raise OllamaError(
                            _format_ollama_http_error(
                                status_code=resp.status_code,
                                body_text=body_text,
                                model=attempt_model,
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
                    return
            except httpx.RequestError as e:
                last_err = OllamaError(f"Cannot connect to Ollama at {base_url}: {e}")
                break
            except OllamaError as e:
                last_err = e
                continue

        if last_err is not None:
            raise last_err
        raise OllamaError("Unknown Ollama error")


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
        attempt_models: list[str] = [model]
        fallback = None
        if model:
            fallback = _pick_fallback_model(exclude=model)
        if fallback:
            attempt_models.append(fallback)

        last_err: OllamaError | None = None
        for attempt_model in attempt_models:
            payload["model"] = attempt_model
            try:
                resp = await client.post(url, json=payload)
            except httpx.RequestError as e:
                raise OllamaError(f"Cannot connect to Ollama at {base_url}: {e}") from e

            if resp.status_code >= 400:
                if attempt_model == model and _is_model_not_found(status_code=resp.status_code, body_text=resp.text) and fallback:
                    logger.warning(
                        "Ollama model '%s' not found; falling back to installed model '%s'",
                        model,
                        fallback,
                    )
                    continue
                last_err = OllamaError(
                    _format_ollama_http_error(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        model=attempt_model,
                    )
                )
                continue

            data = resp.json()
            msg = (data.get("message") or {}).get("content")
            return (msg or "").strip()

        if last_err is not None:
            raise last_err
        raise OllamaError("Unknown Ollama error")
