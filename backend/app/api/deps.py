from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import AuthError, decode_access_token
from app.core.settings import settings
from app.db.models import User
from app.db.session import get_session
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


async def require_auth(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User | None:
    """Require either a valid API key (if configured) or a valid JWT.

    - If `AGENTPRESS_API_KEY` is set and matches, request is allowed (returns None).
    - Otherwise a Bearer JWT is required (returns the User).

    This keeps backward compatibility with existing API-key protected flows while
    enabling user auth for browser clients.
    """

    if getattr(settings, "auth_disabled", False):
        return None

    expected_key = (settings.api_key or "").strip()
    has_jwt = bool((settings.jwt_secret or "").strip())

    # Back-compat / dev default: if neither API key nor JWT is configured, allow all.
    if not expected_key and not has_jwt:
        return None

    if expected_key:
        token_key = (x_api_key or "").strip()
        if not token_key and authorization:
            parts = authorization.strip().split(" ", 1)
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token_key = parts[1].strip()
        if hmac.compare_digest(token_key, expected_key):
            return None

    bearer = (authorization or "").strip()
    if not bearer.lower().startswith("bearer "):
        # Optional cookie auth for browser clients.
        if settings.auth_cookie_enabled:
            cookie_name = (settings.auth_cookie_name or "").strip() or "agentpress_access_token"
            cookie_token = (request.cookies.get(cookie_name) or "").strip()
            if cookie_token:
                bearer = f"Bearer {cookie_token}"

    if not bearer.lower().startswith("bearer "):
        if settings.audit_enabled:
            client_ip = request.client.host if request.client else None
            _auth_failures.append(
                AuthFailureEvent(
                    ts_ms=now_ms(),
                    method=request.method,
                    path=request.url.path,
                    client_ip=client_ip,
                    reason="missing_bearer_token",
                )
            )
        raise HTTPException(status_code=401, detail="unauthorized")

    jwt_token = bearer.split(" ", 1)[1].strip()
    try:
        claims = decode_access_token(jwt_token)
    except AuthError:
        if settings.audit_enabled:
            client_ip = request.client.host if request.client else None
            _auth_failures.append(
                AuthFailureEvent(
                    ts_ms=now_ms(),
                    method=request.method,
                    path=request.url.path,
                    client_ip=client_ip,
                    reason="invalid_jwt",
                )
            )
        raise HTTPException(status_code=401, detail="unauthorized")

    res = await session.execute(select(User).where(User.id == claims.sub))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")

    return user
