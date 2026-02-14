from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request

from app.core.settings import settings
from app.security.audit import AuthFailureEvent, InMemoryAuditLog, now_ms


_auth_failures = InMemoryAuditLog(max_events=settings.audit_max_events)


def list_auth_failures(*, limit: int = 200) -> list[dict]:
    return _auth_failures.list(limit=limit)


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Optional API key auth.

    If `AGENTPRESS_API_KEY` is unset, this dependency allows all requests.
    If set, clients must send either:
      - `X-API-Key: <key>`
      - `Authorization: Bearer <key>`
    """

    expected = (settings.api_key or "").strip()
    if not expected:
        return

    token = (x_api_key or "").strip()
    if not token and authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()

    if not hmac.compare_digest(token, expected):
        if settings.audit_enabled:
            client_ip = request.client.host if request.client else None
            _auth_failures.append(
                AuthFailureEvent(
                    ts_ms=now_ms(),
                    method=request.method,
                    path=request.url.path,
                    client_ip=client_ip,
                    reason="invalid_api_key",
                )
            )
        raise HTTPException(status_code=401, detail="unauthorized")
