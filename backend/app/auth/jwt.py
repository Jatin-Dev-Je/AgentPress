from __future__ import annotations

import time
from dataclasses import dataclass

import jwt

from app.core.settings import settings


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class JwtClaims:
    sub: str
    email: str | None
    name: str | None


def _require_jwt_secret() -> str:
    secret = (settings.jwt_secret or "").strip()
    if not secret:
        raise AuthError("JWT is not configured (missing AGENTPRESS_JWT_SECRET)")
    return secret


def create_access_token(*, user_id: str, email: str | None, name: str | None) -> str:
    secret = _require_jwt_secret()
    now = int(time.time())
    exp = now + int(max(1, settings.jwt_access_token_minutes)) * 60

    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "iat": now,
        "nbf": now,
        "exp": exp,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "typ": "access",
    }

    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> JwtClaims:
    secret = _require_jwt_secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as e:  # type: ignore[attr-defined]
        raise AuthError("invalid_token") from e

    if payload.get("typ") != "access":
        raise AuthError("invalid_token_type")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("invalid_subject")

    email = payload.get("email")
    if email is not None and not isinstance(email, str):
        email = None

    name = payload.get("name")
    if name is not None and not isinstance(name, str):
        name = None

    return JwtClaims(sub=sub, email=email, name=name)
