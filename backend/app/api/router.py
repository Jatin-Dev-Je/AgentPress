from fastapi import APIRouter

from app.api.routes import agents
from app.api.routes import audit
from app.api.routes import plugins

api_router = APIRouter()
api_router.include_router(
	agents.router,
	prefix="/agents",
	tags=["agents"],
)
api_router.include_router(
	plugins.router,
	prefix="/plugins",
	tags=["plugins"],
)

api_router.include_router(
	audit.router,
	prefix="/audit",
	tags=["audit"],
)
