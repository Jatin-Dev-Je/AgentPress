from fastapi import APIRouter, Depends

from app.api.routes import agents
from app.api.routes import audit
from app.api.routes import auth
from app.api.routes import plugins
from app.api.deps import require_auth

api_router = APIRouter()
api_router.include_router(
	auth.router,
	prefix="/auth",
	tags=["auth"],
)

api_router.include_router(
	agents.router,
	prefix="/agents",
	tags=["agents"],
	dependencies=[Depends(require_auth)],
)
api_router.include_router(
	plugins.router,
	prefix="/plugins",
	tags=["plugins"],
	dependencies=[Depends(require_auth)],
)

api_router.include_router(
	audit.router,
	prefix="/audit",
	tags=["audit"],
	dependencies=[Depends(require_auth)],
)
