from fastapi import FastAPI

from app.api.router import api_router
from app.core.settings import settings
from app.db.init_db import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="Agentpress", version="0.1.0")
    app.include_router(api_router)

    @app.on_event("startup")
    async def _startup() -> None:
        await init_db()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "plugins_dir": str(settings.plugins_dir)}

    return app


app = create_app()
