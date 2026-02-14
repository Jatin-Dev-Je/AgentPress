from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.settings import settings
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
        return {"status": "ok", "plugins_dir": str(settings.plugins_dir)}

    return app


app = create_app()
