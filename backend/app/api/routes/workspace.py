"""Background analysis, recommendations and case inspection endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.schemas.workspace import (
    AnalysisJob,
    AnalysisJobRequest,
    CaseDetail,
    CasePage,
    RecommendationPage,
)

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Analysis workspace"])
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=200)]


@router.post("/analysis-jobs", response_model=AnalysisJob, status_code=202)
def start_job(dataset_id: UUID, body: AnalysisJobRequest, request: Request):
    return request.app.state.jobs.start(str(dataset_id), body)


@router.get("/analysis-jobs/latest", response_model=AnalysisJob)
def latest_job(dataset_id: UUID, request: Request):
    return request.app.state.jobs.latest(str(dataset_id))


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJob)
def job(dataset_id: UUID, job_id: UUID, request: Request):
    return request.app.state.jobs.get(str(dataset_id), str(job_id))


@router.get("/recommendations", response_model=RecommendationPage)
def recommendations(
    dataset_id: UUID,
    request: Request,
    offset: Offset = 0,
    limit: Limit = 50,
    process_id: str | None = None,
):
    return request.app.state.workspace.recommendations(str(dataset_id), offset, limit, process_id)


@router.get("/cases", response_model=CasePage)
def cases(
    dataset_id: UUID,
    request: Request,
    offset: Offset = 0,
    limit: Limit = 50,
    process_id: str | None = None,
    variant_id: str | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
):
    return request.app.state.workspace.cases(
        str(dataset_id), offset, limit, process_id, variant_id, search
    )


@router.get("/cases/{case_id}", response_model=CaseDetail)
def case(dataset_id: UUID, case_id: str, request: Request, offset: Offset = 0, limit: Limit = 100):
    return request.app.state.workspace.case(str(dataset_id), case_id, offset, limit)
