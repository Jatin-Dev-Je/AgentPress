from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.settings import settings
from app.db.session import engine
from app.db.init_db import init_db
from app.security.middleware import FixedWindowRateLimitMiddleware, MaxBodySizeMiddleware, SecurityHeadersMiddleware


def create_app() -> FastAPI:
    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None
    openapi_url = "/openapi.json" if settings.enable_docs else None

    app = FastAPI(
        title="Agentpress",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Security middleware (apply before routes).
    app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.max_request_body_bytes)
    if settings.security_headers_enabled:
        app.add_middleware(
            SecurityHeadersMiddleware,
            hsts_enabled=settings.hsts_enabled,
            hsts_max_age_seconds=settings.hsts_max_age_seconds,
        )
    if settings.rate_limit_enabled:
        app.add_middleware(
            FixedWindowRateLimitMiddleware,
            requests_per_minute=settings.rate_limit_requests_per_minute,
            trust_proxy_headers=settings.trust_proxy_headers,
            exempt_paths={"/health"},
        )

    if settings.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
            allow_credentials=settings.cors_allow_credentials,
        )

    app.include_router(api_router)

    @app.on_event("startup")
    async def _startup() -> None:
        await init_db()

    @app.get("/health")
    async def health() -> dict:
        checks: dict[str, dict] = {}

        async def _db_check() -> None:
            t0 = time.perf_counter()
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                checks["db"] = {"ok": True, "ms": int((time.perf_counter() - t0) * 1000)}
            except Exception as e:
                checks["db"] = {
                    "ok": False,
                    "ms": int((time.perf_counter() - t0) * 1000),
                    "error": str(e),
                }

        async def _redis_check() -> None:
            if not settings.redis_url:
                return
            t0 = time.perf_counter()
            try:
                u = urlparse(settings.redis_url)
                host = u.hostname
                port = u.port or 6379
                if not host:
                    raise ValueError("redis_url missing hostname")
                reader, writer = await asyncio.open_connection(host, port)
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                checks["redis"] = {"ok": True, "ms": int((time.perf_counter() - t0) * 1000)}
            except Exception as e:
                checks["redis"] = {
                    "ok": False,
                    "ms": int((time.perf_counter() - t0) * 1000),
                    "error": str(e),
                }

        async def _qdrant_check() -> None:
            if not settings.qdrant_url:
                return
            t0 = time.perf_counter()
            try:
                base = settings.qdrant_url.rstrip("/")
                async with httpx.AsyncClient(timeout=settings.healthcheck_timeout_seconds) as client:
                    for path in ("/healthz", "/readyz", "/collections"):
                        r = await client.get(base + path)
                        if 200 <= r.status_code < 300:
                            checks["qdrant"] = {
                                "ok": True,
                                "ms": int((time.perf_counter() - t0) * 1000),
                                "path": path,
                            }
                            return
                    checks["qdrant"] = {
                        "ok": False,
                        "ms": int((time.perf_counter() - t0) * 1000),
                        "error": f"unexpected status from {base} (tried /healthz,/readyz,/collections)",
                    }
            except Exception as e:
                checks["qdrant"] = {
                    "ok": False,
                    "ms": int((time.perf_counter() - t0) * 1000),
                    "error": str(e),
                }

        timeout = max(0.1, float(settings.healthcheck_timeout_seconds))
        await asyncio.gather(
            asyncio.wait_for(_db_check(), timeout=timeout),
            asyncio.wait_for(_redis_check(), timeout=timeout),
            asyncio.wait_for(_qdrant_check(), timeout=timeout),
            return_exceptions=True,
        )

        ok = all(v.get("ok") is True for v in checks.values()) if checks else True
        status = "ok" if ok else "degraded"

        return {
            "status": status,
            "plugins_dir": str(settings.plugins_dir),
            "checks": checks,
        }

    return app


app = create_app()
