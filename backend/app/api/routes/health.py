"""Application liveness without triggering data loading or analysis."""

from fastapi import APIRouter, Request

from app import __version__
from app.schemas.common import HealthResponse

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse, summary="Check API health")
async def health(request: Request) -> HealthResponse:
    return HealthResponse(version=__version__, environment=request.app.state.settings.app_env)
