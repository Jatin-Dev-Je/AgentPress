from __future__ import annotations

import secrets
from datetime import datetime
from urllib.parse import quote

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


def _pop_state_cookie(request: Request, provider: str) -> str | None:
    return request.cookies.get(_state_cookie_name(provider))


def _clear_state_cookie(resp: RedirectResponse, provider: str) -> None:
    resp.delete_cookie(key=_state_cookie_name(provider), path=f"/auth/oauth/{provider}")


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

    scope = "openid email profile"
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.google_oauth_client_id}"
        f"&redirect_uri={settings.google_oauth_redirect_uri}"
        "&response_type=code"
        f"&scope={quote(scope)}"
        f"&state={state}"
        "&include_granted_scopes=true"
    )

    resp = RedirectResponse(url=url)
    _set_state_cookie(resp, provider="google", state=state, secure=(request.url.scheme == "https"))
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
        raise HTTPException(status_code=400, detail="invalid oauth state")

    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret or not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="google oauth not configured")

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
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=400, detail="oauth token exchange failed")
        token = r.json()
        access_token = token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(status_code=400, detail="oauth token missing")

        u = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        if u.status_code >= 400:
            raise HTTPException(status_code=400, detail="oauth userinfo failed")
        profile = u.json()

    provider_user_id = profile.get("sub")
    email = profile.get("email")
    name = profile.get("name")
    picture = profile.get("picture")

    if not isinstance(provider_user_id, str) or not provider_user_id:
        raise HTTPException(status_code=400, detail="oauth profile missing sub")
    if not isinstance(email, str) or not email:
        raise HTTPException(status_code=400, detail="oauth profile missing email")

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
        raise HTTPException(status_code=500, detail=str(e))

    resp = JSONResponse({"access_token": jwt_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}})
    resp.delete_cookie(key=_state_cookie_name("google"), path="/auth/oauth/google")
    return resp


@router.get("/oauth/github/login")
async def github_login(request: Request) -> RedirectResponse:
    if not settings.github_oauth_client_id or not settings.github_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="github oauth not configured")

    state = secrets.token_urlsafe(32)
    scope = "read:user user:email"

    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_oauth_client_id}"
        f"&redirect_uri={settings.github_oauth_redirect_uri}"
        f"&scope={quote(scope)}"
        f"&state={state}"
    )

    resp = RedirectResponse(url=url)
    _set_state_cookie(resp, provider="github", state=state, secure=(request.url.scheme == "https"))
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
        raise HTTPException(status_code=400, detail="invalid oauth state")

    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret or not settings.github_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="github oauth not configured")

    token_url = "https://github.com/login/oauth/access_token"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            token_url,
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=400, detail="oauth token exchange failed")
        token = r.json()
        access_token = token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(status_code=400, detail="oauth token missing")

        u = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
        if u.status_code >= 400:
            raise HTTPException(status_code=400, detail="oauth userinfo failed")
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
        raise HTTPException(status_code=400, detail="oauth profile missing id")
    if not email:
        raise HTTPException(status_code=400, detail="oauth profile missing email")

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
        raise HTTPException(status_code=500, detail=str(e))

    resp = JSONResponse({"access_token": jwt_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}})
    resp.delete_cookie(key=_state_cookie_name("github"), path="/auth/oauth/github")
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
