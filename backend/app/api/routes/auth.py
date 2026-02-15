from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.auth.jwt import AuthError, create_access_token
from app.core.settings import settings
from app.db.models import OAuthAccount, User
from app.db.session import get_session


router = APIRouter()


def _state_cookie_name(provider: str) -> str:
    return f"agentpress_oauth_state_{provider}"


def _pkce_cookie_name(provider: str) -> str:
    return f"agentpress_oauth_pkce_{provider}"


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _set_state_cookie(resp: RedirectResponse, *, provider: str, state: str, secure: bool) -> None:
    resp.set_cookie(
        key=_state_cookie_name(provider),
        value=state,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=10 * 60,
        path=f"/auth/oauth/{provider}",
    )


def _set_pkce_cookie(resp: RedirectResponse, *, provider: str, verifier: str, secure: bool) -> None:
    resp.set_cookie(
        key=_pkce_cookie_name(provider),
        value=verifier,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=10 * 60,
        path=f"/auth/oauth/{provider}",
    )


def _pop_state_cookie(request: Request, provider: str) -> str | None:
    return request.cookies.get(_state_cookie_name(provider))


def _pop_pkce_cookie(request: Request, provider: str) -> str | None:
    return request.cookies.get(_pkce_cookie_name(provider))


def _clear_state_cookie(resp: RedirectResponse, provider: str) -> None:
    resp.delete_cookie(key=_state_cookie_name(provider), path=f"/auth/oauth/{provider}")


def _clear_pkce_cookie(resp: RedirectResponse, provider: str) -> None:
    resp.delete_cookie(key=_pkce_cookie_name(provider), path=f"/auth/oauth/{provider}")


def _maybe_set_auth_cookie(resp: JSONResponse | RedirectResponse, request: Request, jwt_token: str) -> None:
    if not settings.auth_cookie_enabled:
        return
    cookie_name = (settings.auth_cookie_name or "").strip() or "agentpress_access_token"
    max_age = int(max(1, settings.jwt_access_token_minutes)) * 60
    resp.set_cookie(
        key=cookie_name,
        value=jwt_token,
        httponly=True,
        secure=(request.url.scheme == "https"),
        samesite=settings.auth_cookie_samesite,
        max_age=max_age,
        domain=settings.auth_cookie_domain,
        path=settings.auth_cookie_path,
    )


def _auth_success_response(request: Request, *, jwt_token: str, user: User, provider: str) -> JSONResponse | RedirectResponse:
    if settings.auth_redirect_success_url:
        resp: RedirectResponse | JSONResponse = RedirectResponse(url=settings.auth_redirect_success_url)
    else:
        resp = JSONResponse(
            {
                "access_token": jwt_token,
                "token_type": "bearer",
                "user": {"id": user.id, "email": user.email},
            }
        )

    _maybe_set_auth_cookie(resp, request, jwt_token)
    resp.delete_cookie(key=_state_cookie_name(provider), path=f"/auth/oauth/{provider}")
    resp.delete_cookie(key=_pkce_cookie_name(provider), path=f"/auth/oauth/{provider}")
    return resp


def _append_query(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def _oauth_error(provider: str, *, request: Request, status_code: int, error: str) -> RedirectResponse:
    """OAuth callback error handler.

    If `AGENTPRESS_AUTH_REDIRECT_ERROR_URL` is set, redirect there with `?error=...`.
    Otherwise, raise an HTTPException.
    """

    if not settings.auth_redirect_error_url:
        raise HTTPException(status_code=status_code, detail=error)

    url = _append_query(settings.auth_redirect_error_url, {"error": error, "provider": provider})
    resp = RedirectResponse(url=url)
    resp.delete_cookie(key=_state_cookie_name(provider), path=f"/auth/oauth/{provider}")
    resp.delete_cookie(key=_pkce_cookie_name(provider), path=f"/auth/oauth/{provider}")
    return resp


@router.get("/me")
async def me(user: User | None = Depends(require_auth)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.get("/oauth/google/login")
async def google_login(request: Request) -> RedirectResponse:
    if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="google oauth not configured")

    state = secrets.token_urlsafe(32)
    secure = request.url.scheme == "https"

    params: dict[str, str] = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "include_granted_scopes": "true",
    }

    # Optional PKCE (disabled by default; can be enabled later via env var)
    if getattr(settings, "oauth_pkce_enabled", False):
        verifier = secrets.token_urlsafe(48)
        params["code_challenge"] = _pkce_challenge(verifier)
        params["code_challenge_method"] = "S256"

    url = "https://accounts.google.com/o/oauth2/v2/auth" + "?" + urlencode(params)

    resp = RedirectResponse(url=url)
    _set_state_cookie(resp, provider="google", state=state, secure=secure)
    if getattr(settings, "oauth_pkce_enabled", False):
        _set_pkce_cookie(resp, provider="google", verifier=verifier, secure=secure)  # type: ignore[name-defined]
    return resp


@router.get("/oauth/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = _pop_state_cookie(request, "google")
    if not expected or expected != state:
        return _oauth_error("google", request=request, status_code=400, error="invalid_oauth_state")

    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret or not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="google oauth not configured")

    code_verifier = None
    if getattr(settings, "oauth_pkce_enabled", False):
        code_verifier = _pop_pkce_cookie(request, "google")

    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            token_url,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
                **({"code_verifier": code_verifier} if code_verifier else {}),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 400:
            return _oauth_error("google", request=request, status_code=400, error="oauth_token_exchange_failed")
        token = r.json()
        access_token = token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return _oauth_error("google", request=request, status_code=400, error="oauth_token_missing")

        u = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        if u.status_code >= 400:
            return _oauth_error("google", request=request, status_code=400, error="oauth_userinfo_failed")
        profile = u.json()

    provider_user_id = profile.get("sub")
    email = profile.get("email")
    name = profile.get("name")
    picture = profile.get("picture")

    if not isinstance(provider_user_id, str) or not provider_user_id:
        return _oauth_error("google", request=request, status_code=400, error="oauth_profile_missing_sub")
    if not isinstance(email, str) or not email:
        return _oauth_error("google", request=request, status_code=400, error="oauth_profile_missing_email")

    user = await _upsert_oauth_user(
        session=session,
        provider="google",
        provider_user_id=provider_user_id,
        email=email,
        name=name if isinstance(name, str) else None,
        avatar_url=picture if isinstance(picture, str) else None,
    )

    try:
        jwt_token = create_access_token(user_id=user.id, email=user.email, name=user.name)
    except AuthError as e:
        return _oauth_error("google", request=request, status_code=500, error=str(e))

    return _auth_success_response(request, jwt_token=jwt_token, user=user, provider="google")


@router.get("/oauth/github/login")
async def github_login(request: Request) -> RedirectResponse:
    if not settings.github_oauth_client_id or not settings.github_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="github oauth not configured")

    state = secrets.token_urlsafe(32)
    secure = request.url.scheme == "https"

    params: dict[str, str] = {
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }

    if getattr(settings, "oauth_pkce_enabled", False):
        verifier = secrets.token_urlsafe(48)
        params["code_challenge"] = _pkce_challenge(verifier)
        params["code_challenge_method"] = "S256"

    url = "https://github.com/login/oauth/authorize" + "?" + urlencode(params)

    resp = RedirectResponse(url=url)
    _set_state_cookie(resp, provider="github", state=state, secure=secure)
    if getattr(settings, "oauth_pkce_enabled", False):
        _set_pkce_cookie(resp, provider="github", verifier=verifier, secure=secure)  # type: ignore[name-defined]
    return resp


@router.get("/oauth/github/callback")
async def github_callback(
    request: Request,
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = _pop_state_cookie(request, "github")
    if not expected or expected != state:
        return _oauth_error("github", request=request, status_code=400, error="invalid_oauth_state")

    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret or not settings.github_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="github oauth not configured")

    code_verifier = None
    if getattr(settings, "oauth_pkce_enabled", False):
        code_verifier = _pop_pkce_cookie(request, "github")

    token_url = "https://github.com/login/oauth/access_token"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            token_url,
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
                **({"code_verifier": code_verifier} if code_verifier else {}),
            },
            headers={"Accept": "application/json"},
        )
        if r.status_code >= 400:
            return _oauth_error("github", request=request, status_code=400, error="oauth_token_exchange_failed")
        token = r.json()
        access_token = token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return _oauth_error("github", request=request, status_code=400, error="oauth_token_missing")

        u = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
        if u.status_code >= 400:
            return _oauth_error("github", request=request, status_code=400, error="oauth_userinfo_failed")
        profile = u.json()

        emails = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
        email_list = emails.json() if emails.status_code < 400 else []

    provider_user_id = str(profile.get("id") or "")
    name = profile.get("name") or profile.get("login")
    avatar_url = profile.get("avatar_url")

    email = None
    if isinstance(profile.get("email"), str) and profile.get("email"):
        email = profile.get("email")
    else:
        if isinstance(email_list, list):
            primary = None
            for e in email_list:
                if not isinstance(e, dict):
                    continue
                if e.get("primary") is True and e.get("verified") is True:
                    primary = e
                    break
            if primary is None:
                for e in email_list:
                    if isinstance(e, dict) and e.get("verified") is True:
                        primary = e
                        break
            if primary and isinstance(primary.get("email"), str):
                email = primary.get("email")

    if not provider_user_id:
        return _oauth_error("github", request=request, status_code=400, error="oauth_profile_missing_id")
    if not email:
        return _oauth_error("github", request=request, status_code=400, error="oauth_profile_missing_email")

    user = await _upsert_oauth_user(
        session=session,
        provider="github",
        provider_user_id=provider_user_id,
        email=email,
        name=name if isinstance(name, str) else None,
        avatar_url=avatar_url if isinstance(avatar_url, str) else None,
    )

    try:
        jwt_token = create_access_token(user_id=user.id, email=user.email, name=user.name)
    except AuthError as e:
        return _oauth_error("github", request=request, status_code=500, error=str(e))

    return _auth_success_response(request, jwt_token=jwt_token, user=user, provider="github")


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    if not settings.auth_cookie_enabled:
        return JSONResponse({"ok": True})

    cookie_name = (settings.auth_cookie_name or "").strip() or "agentpress_access_token"
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(
        key=cookie_name,
        domain=settings.auth_cookie_domain,
        path=settings.auth_cookie_path,
    )
    return resp


async def _upsert_oauth_user(
    *,
    session: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    name: str | None,
    avatar_url: str | None,
) -> User:
    res = await session.execute(
        select(OAuthAccount).where(OAuthAccount.provider == provider, OAuthAccount.provider_user_id == provider_user_id)
    )
    acct = res.scalar_one_or_none()
    if acct is not None:
        res2 = await session.execute(select(User).where(User.id == acct.user_id))
        user = res2.scalar_one()
    else:
        res2 = await session.execute(select(User).where(User.email == email))
        user = res2.scalar_one_or_none()
        if user is None:
            user = User(email=email, name=name, avatar_url=avatar_url)
            session.add(user)
            await session.commit()
            await session.refresh(user)

        acct = OAuthAccount(user_id=user.id, provider=provider, provider_user_id=provider_user_id)
        session.add(acct)

    user.last_login_at = datetime.utcnow()
    if name and not user.name:
        user.name = name
    if avatar_url and not user.avatar_url:
        user.avatar_url = avatar_url

    await session.commit()
    await session.refresh(user)
    return user
