from fastapi import APIRouter, Depends

from app.api.routes import agents
from app.api.routes import plugins
from app.api.deps import require_api_key

api_router = APIRouter()
api_router.include_router(
	agents.router,
	prefix="/agents",
	tags=["agents"],
	dependencies=[Depends(require_api_key)],
)
api_router.include_router(
	plugins.router,
	prefix="/plugins",
	tags=["plugins"],
	dependencies=[Depends(require_api_key)],
)
