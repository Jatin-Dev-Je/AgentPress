from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.core.settings import settings


def require_api_key(
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
        raise HTTPException(status_code=401, detail="unauthorized")
