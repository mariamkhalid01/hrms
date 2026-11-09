"""FastAPI entrypoint and application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import Settings
from app.core.errors import register_error_handlers
from app.core.middleware import RequestContextMiddleware
from app.schemas.common import ErrorResponse
from app.services.ingestion.limits import UploadSizeLimitMiddleware
from app.services.orchestration.analytics import AnalyticsService
from app.services.orchestration.datasets import DatasetService
from app.services.orchestration.discovery import DiscoveryService
from app.services.orchestration.jobs import AnalysisJobService
from app.services.orchestration.workspace import WorkspaceService


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    logger = logging.getLogger("hr_process_mining")
    logger.setLevel(config.log_level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False

    @asynccontextmanager
    async def lifespan(instance):
        yield
        instance.state.jobs.shutdown()

    application = FastAPI(
        title="HR Process Mining API",
        version=__version__,
        description="Backend for the HR Process Mining and Improvement Platform.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        responses={
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    application.state.settings = config
    application.state.datasets = DatasetService(config)
    application.state.discovery = DiscoveryService(application.state.datasets)
    application.state.analytics = AnalyticsService(application.state.discovery)
    application.state.workspace = WorkspaceService(application.state.analytics)
    application.state.jobs = AnalysisJobService(application.state.workspace)
    register_error_handlers(application)
    application.include_router(api_router)
    application.add_middleware(
        UploadSizeLimitMiddleware, max_body_bytes=config.max_upload_bytes + 65_536
    )
    application.add_middleware(RequestContextMiddleware)
    # CORS wraps the error middleware so sanitized 500 responses retain CORS headers.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    return application


app = create_app()
