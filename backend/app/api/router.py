"""The public v1 route collection."""

from fastapi import APIRouter

from app.api.routes.analytics import router as analytics_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.health import router as health_router
from app.api.routes.workspace import router as workspace_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(datasets_router)
api_router.include_router(discovery_router)
api_router.include_router(analytics_router)
api_router.include_router(workspace_router)
