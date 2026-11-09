"""Typed performance and finding routes, suitable for charts and map inspection."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.schemas.analytics import (
    AnalyticsRequest,
    AnalyticsResult,
    FindingCategory,
    FindingsPage,
    PerformanceVariantsPage,
    ProcessPerformance,
)

router = APIRouter(prefix="/datasets/{dataset_id}/analytics", tags=["Performance and bottlenecks"])


@router.post("", response_model=AnalyticsResult)
def analyze(dataset_id: UUID, body: AnalyticsRequest, request: Request) -> dict:
    return request.app.state.analytics.run(str(dataset_id), body)


@router.get("", response_model=AnalyticsResult)
def result(dataset_id: UUID, request: Request) -> dict:
    return request.app.state.analytics.result(str(dataset_id))


@router.get("/processes/{process_id}", response_model=ProcessPerformance)
def process(dataset_id: UUID, process_id: str, request: Request) -> dict:
    return request.app.state.analytics.process(str(dataset_id), process_id)


@router.get("/processes/{process_id}/variants", response_model=PerformanceVariantsPage)
def variants(
    dataset_id: UUID,
    process_id: str,
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    return request.app.state.analytics.variants(str(dataset_id), process_id, offset, limit)


@router.get("/findings", response_model=FindingsPage)
def findings(
    dataset_id: UUID,
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    process_id: str | None = None,
    category: FindingCategory | None = None,
    severity: Literal["low", "medium", "high"] | None = None,
    entity_id: str | None = None,
) -> dict:
    return request.app.state.analytics.findings(
        str(dataset_id), offset, limit, process_id, category, severity, entity_id
    )
