from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class GeminiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    def is_rate_limited(self) -> bool:
        sc = self.status_code
        msg = (str(self) or "").lower()
        if sc == 429:
            return True
        if sc == 403 and ("quota" in msg or "rate" in msg or "exceed" in msg):
            return True
        return "rate limit" in msg or "quota" in msg

    def is_model_not_found(self) -> bool:
        if self.status_code != 404:
            return False
        msg = (str(self) or "").lower()
        return "model" in msg and "not found" in msg


def _normalize_model(model: str) -> str:
    m = (model or "").strip()
    if not m:
        raise GeminiError("Gemini model is required")
    if not m.startswith("models/"):
        m = "models/" + m
    return m


def _base_with_version(base_url: str, api_version: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise GeminiError("Gemini base_url is required")

    # Allow callers to pass either the host (recommended) or a versioned base.
    if base.endswith("/v1") or base.endswith("/v1beta"):
        root = base.rsplit("/", 1)[0]
        return f"{root}/{api_version}"
    return f"{base}/{api_version}"


async def _list_models(
    *,
    client: httpx.AsyncClient,
    api_key: str,
    base_url: str,
    api_version: str,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    url = f"{_base_with_version(base_url, api_version)}/models"
    try:
        resp = await client.get(url, params={"key": api_key}, timeout=timeout_seconds)
    except httpx.RequestError as e:
        raise GeminiError(f"Cannot connect to Gemini at {base_url}: {e}") from e

    if resp.status_code >= 400:
        raise GeminiError(
            _format_gemini_http_error(resp.status_code, resp.text),
            status_code=resp.status_code,
        )

    data = resp.json()
    models = data.get("models") if isinstance(data, dict) else None
    if isinstance(models, list):
        out: list[dict[str, Any]] = []
        for m in models:
            if isinstance(m, dict):
                out.append(m)
        return out
    return []


def _pick_model_name(
    *,
    models: list[dict[str, Any]],
    requested: str,
    required_method: str,
) -> str | None:
    requested_raw = (requested or "").strip()
    requested_norm = _normalize_model(requested_raw) if requested_raw else None

    candidates: list[str] = []
    for m in models:
        name = m.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        methods = m.get("supportedGenerationMethods")
        if isinstance(methods, list) and required_method not in methods:
            continue
        candidates.append(name.strip())

    if not candidates:
        return None

    if requested_norm and requested_norm in candidates:
        return requested_norm

    if requested_raw:
        # Exact short-name match.
        for name in candidates:
            if name.endswith("/" + requested_raw):
                return name

        # Substring match.
        req_l = requested_raw.lower()
        for name in candidates:
            if req_l in name.lower():
                return name

    # Prefer a flash model when picking a default.
    for name in candidates:
        if "flash" in name.lower():
            return name
    return candidates[0]


def _extract_text_from_response(data: dict) -> str:
    # Typical response structure:
    # { candidates: [ { content: { parts: [ {text: "..."} ] } } ] }
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        c0 = candidates[0] if isinstance(candidates[0], dict) else None
        content = (c0 or {}).get("content") if isinstance(c0, dict) else None
        if isinstance(content, dict):
            parts = content.get("parts")
            if isinstance(parts, list):
                texts: list[str] = []
                for p in parts:
                    if isinstance(p, dict) and isinstance(p.get("text"), str):
                        texts.append(p["text"])
                return "".join(texts)
    return ""


def _messages_to_gemini_payload(*, messages: list[dict], temperature: float | None) -> dict[str, Any]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []

    for m in messages:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "")
        if not isinstance(content, str):
            content = str(content)

        if role == "system":
            if content:
                system_parts.append(content)
            continue

        if role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            # Ignore tool/system-like roles for now.
            continue

    payload: dict[str, Any] = {"contents": contents}
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    if temperature is not None:
        payload["generationConfig"] = {"temperature": float(temperature)}
    return payload


def _format_gemini_http_error(status_code: int, body_text: str) -> str:
    # Gemini errors are typically: {"error": {"message": "...", "status": "..."}}
    try:
        data = json.loads(body_text)
    except Exception:
        data = None

    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            if isinstance(msg, str) and msg.strip():
                return f"Gemini error {status_code}: {msg.strip()}"
    return f"Gemini error {status_code}: {body_text}"


async def chat_once(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    timeout_seconds: float = 60.0,
) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise GeminiError("Gemini base_url is required")

    key = (api_key or "").strip()
    if not key:
        raise GeminiError("Gemini API key is not configured (set AGENTPRESS_GEMINI_API_KEY)")

    payload = _messages_to_gemini_payload(messages=messages, temperature=temperature)

    timeout = httpx.Timeout(timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        m0 = _normalize_model(model)
        last_err: GeminiError | None = None
        for api_version in ("v1", "v1beta"):
            base_v = _base_with_version(base, api_version)

            # First try the requested model.
            url = f"{base_v}/{m0}:generateContent"
            try:
                resp = await client.post(url, params={"key": key}, json=payload)
            except httpx.RequestError as e:
                raise GeminiError(f"Cannot connect to Gemini at {base}: {e}") from e

            if resp.status_code == 404:
                # Model not available on this API version. Try to resolve via ListModels.
                try:
                    models_list = await _list_models(
                        client=client,
                        api_key=key,
                        base_url=base,
                        api_version=api_version,
                        timeout_seconds=timeout_seconds,
                    )
                    picked = _pick_model_name(
                        models=models_list,
                        requested=model,
                        required_method="generateContent",
                    )
                except GeminiError as e:
                    last_err = e
                    continue

                if picked and picked != m0:
                    url2 = f"{base_v}/{picked}:generateContent"
                    resp2 = await client.post(url2, params={"key": key}, json=payload)
                    if resp2.status_code >= 400:
                        last_err = GeminiError(
                            _format_gemini_http_error(resp2.status_code, resp2.text),
                            status_code=resp2.status_code,
                        )
                        continue
                    data = resp2.json()
                    return _extract_text_from_response(data).strip()

                last_err = GeminiError(
                    _format_gemini_http_error(resp.status_code, resp.text),
                    status_code=resp.status_code,
                )
                continue

            if resp.status_code >= 400:
                last_err = GeminiError(
                    _format_gemini_http_error(resp.status_code, resp.text),
                    status_code=resp.status_code,
                )
                continue

            data = resp.json()
            return _extract_text_from_response(data).strip()

        if last_err:
            raise last_err
        raise GeminiError("Gemini request failed")


async def stream_chat(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict],
    temperature: float | None = None,
    timeout_seconds: float = 60.0,
) -> AsyncIterator[str]:
    """Yield assistant token-ish chunks from Gemini's streamGenerateContent.

    Gemini streaming returns a sequence of JSON objects (often JSONL, sometimes SSE-ish).
    We parse lines and emit the incremental delta as text.
    """

    base = (base_url or "").rstrip("/")
    if not base:
        raise GeminiError("Gemini base_url is required")

    key = (api_key or "").strip()
    if not key:
        raise GeminiError("Gemini API key is not configured (set AGENTPRESS_GEMINI_API_KEY)")

    payload = _messages_to_gemini_payload(messages=messages, temperature=temperature)

    timeout = httpx.Timeout(timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def _stream_once(*, api_version: str, model_name: str) -> AsyncIterator[str]:
            url = f"{_base_with_version(base, api_version)}/{model_name}:streamGenerateContent"
            async with client.stream("POST", url, params={"key": key}, json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    body_text = body.decode("utf-8", errors="replace")
                    raise GeminiError(
                        _format_gemini_http_error(resp.status_code, body_text),
                        status_code=resp.status_code,
                    )

                # Gemini's streaming endpoint is not guaranteed to return JSONL.
                # In practice it may return a pretty-printed JSON array spanning many lines.
                body = await resp.aread()
                body_text = body.decode("utf-8", errors="replace").strip()
                if not body_text:
                    return

                # Some gateways return SSE-ish framing.
                if body_text.startswith("data:"):
                    lines = []
                    for raw in body_text.splitlines():
                        line = raw.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            line = line[5:].strip()
                        if line == "[DONE]":
                            break
                        lines.append(line)
                    body_text = "\n".join(lines).strip()

                try:
                    parsed = json.loads(body_text)
                except Exception:
                    raise GeminiError(
                        f"Gemini streaming response was not valid JSON: {body_text[:300]}",
                        status_code=resp.status_code,
                    )

                prev = ""
                chunks: list[dict] = []
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            chunks.append(item)
                elif isinstance(parsed, dict):
                    chunks.append(parsed)

                for chunk in chunks:
                    text = _extract_text_from_response(chunk)
                    if not text:
                        continue
                    if text.startswith(prev):
                        delta = text[len(prev) :]
                    else:
                        delta = text
                    prev = text

                    if not delta:
                        continue

                    # Emit as smaller chunks to play nicely with SSE clients.
                    chunk_size = 400
                    for i in range(0, len(delta), chunk_size):
                        yield delta[i : i + chunk_size]

        m0 = _normalize_model(model)
        last_err: GeminiError | None = None
        for api_version in ("v1", "v1beta"):
            try:
                async for t in _stream_once(api_version=api_version, model_name=m0):
                    yield t
                return
            except GeminiError as e:
                last_err = e
                if e.is_model_not_found() or e.status_code == 404:
                    try:
                        models_list = await _list_models(
                            client=client,
                            api_key=key,
                            base_url=base,
                            api_version=api_version,
                            timeout_seconds=timeout_seconds,
                        )
                        picked = _pick_model_name(
                            models=models_list,
                            requested=model,
                            required_method="generateContent",
                        )
                    except GeminiError as e2:
                        last_err = e2
                        continue

                    if picked and picked != m0:
                        try:
                            async for t in _stream_once(api_version=api_version, model_name=picked):
                                yield t
                            return
                        except GeminiError as e3:
                            last_err = e3
                            continue
                continue
            except httpx.RequestError as e:
                raise GeminiError(f"Cannot connect to Gemini at {base}: {e}") from e

        if last_err:
            raise last_err
        raise GeminiError("Gemini streaming request failed")
