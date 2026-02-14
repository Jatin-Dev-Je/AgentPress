from fastapi import FastAPI

from app.api.router import api_router
from app.core.settings import settings
from app.db.init_db import init_db
from app.security.middleware import FixedWindowRateLimitMiddleware, MaxBodySizeMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Agentpress", version="0.1.0")

    # Security middleware (apply before routes).
    app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.max_request_body_bytes)
    if settings.rate_limit_enabled:
        app.add_middleware(
            FixedWindowRateLimitMiddleware,
            requests_per_minute=settings.rate_limit_requests_per_minute,
            trust_proxy_headers=settings.trust_proxy_headers,
            exempt_paths={"/health"},
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
