from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable

from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class MaxBodySizeMiddleware:
    """Reject requests with bodies larger than `max_body_size`.

    This is implemented at the ASGI `receive()` layer so we can stop reading
    the request body as soon as it exceeds the limit.
    """

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max(0, int(max_body_size))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_body_size <= 0:
            await self.app(scope, receive, send)
            return

        # Fast-path: if Content-Length is present and exceeds limit, reject.
        headers = {k.lower(): v for k, v in scope.get("headers") or []}
        if b"content-length" in headers:
            try:
                content_length = int(headers[b"content-length"].decode("ascii", errors="ignore"))
            except Exception:
                content_length = -1
            if content_length > self.max_body_size:
                await self._send_413(send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message.get("type") != "http.request":
                return message

            body = message.get("body") or b""
            received += len(body)
            if received > self.max_body_size:
                # Drain is not necessary; returning 413 ends the response.
                raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._send_413(send)

    async def _send_413(self, send: Send) -> None:
        resp = JSONResponse({"detail": "request body too large"}, status_code=413)
        await resp(scope=None, receive=None, send=send)  # type: ignore[arg-type]


class _BodyTooLarge(Exception):
    pass


@dataclass
class _RateState:
    minute: int
    count: int


class FixedWindowRateLimitMiddleware:
    """Simple in-memory fixed-window rate limiter.

    Notes:
    - Per-process only (works well for single instance / dev). For multi-replica,
      use a shared store (Redis) later.
    - Uses either API key (if present) or client IP as the key.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        requests_per_minute: int,
        trust_proxy_headers: bool = False,
        exempt_paths: set[str] | None = None,
    ) -> None:
        self.app = app
        self.rpm = max(1, int(requests_per_minute))
        self.trust_proxy_headers = bool(trust_proxy_headers)
        self.exempt_paths = exempt_paths or {"/health"}
        self._lock = asyncio.Lock()
        self._states: dict[str, _RateState] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        key = self._key_for_scope(scope)
        now_minute = int(time.time() // 60)

        async with self._lock:
            st = self._states.get(key)
            if st is None or st.minute != now_minute:
                st = _RateState(minute=now_minute, count=0)
                self._states[key] = st

            if st.count >= self.rpm:
                retry_after = 60 - int(time.time() % 60)
                resp = JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
                resp.headers["Retry-After"] = str(max(1, retry_after))
                resp.headers["X-RateLimit-Limit"] = str(self.rpm)
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str((now_minute + 1) * 60)
                await resp(scope=None, receive=None, send=send)  # type: ignore[arg-type]
                return

            st.count += 1
            remaining = max(0, self.rpm - st.count)
            reset_ts = (now_minute + 1) * 60

        async def send_with_headers(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"x-ratelimit-limit", str(self.rpm).encode("ascii")))
                headers.append((b"x-ratelimit-remaining", str(remaining).encode("ascii")))
                headers.append((b"x-ratelimit-reset", str(reset_ts).encode("ascii")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _key_for_scope(self, scope: Scope) -> str:
        headers = {k.lower(): v for k, v in scope.get("headers") or []}

        # Prefer API key identity if present.
        api_key = headers.get(b"x-api-key")
        if api_key:
            return "key:" + api_key.decode("utf-8", errors="ignore")
        auth = headers.get(b"authorization")
        if auth:
            s = auth.decode("utf-8", errors="ignore").strip()
            if s.lower().startswith("bearer "):
                return "key:" + s.split(" ", 1)[1].strip()

        # Otherwise use client IP.
        ip = "unknown"
        if self.trust_proxy_headers:
            xff = headers.get(b"x-forwarded-for")
            if xff:
                ip = xff.decode("utf-8", errors="ignore").split(",", 1)[0].strip() or ip
        if ip == "unknown":
            client = scope.get("client")
            if client and isinstance(client, (list, tuple)) and len(client) >= 1:
                ip = str(client[0])
        return "ip:" + ip


class SecurityHeadersMiddleware:
    """Apply conservative security headers to HTTP responses."""

    def __init__(self, app: ASGIApp, *, hsts_enabled: bool = False, hsts_max_age_seconds: int = 31_536_000) -> None:
        self.app = app
        self.hsts_enabled = bool(hsts_enabled)
        self.hsts_max_age_seconds = int(hsts_max_age_seconds)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])

                def _add(name: bytes, value: bytes) -> None:
                    headers.append((name, value))

                _add(b"x-content-type-options", b"nosniff")
                _add(b"x-frame-options", b"DENY")
                _add(b"referrer-policy", b"no-referrer")
                _add(b"cross-origin-resource-policy", b"same-origin")
                _add(b"permissions-policy", b"geolocation=(), microphone=(), camera=()")

                if self.hsts_enabled:
                    v = f"max-age={max(0, self.hsts_max_age_seconds)}; includeSubDomains".encode("ascii")
                    _add(b"strict-transport-security", v)

                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
