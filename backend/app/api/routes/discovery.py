"""Mining runs in FastAPI worker threads, separate from upload/confirmation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.schemas.discovery import DiscoveryRequest, DiscoveryResult, ProcessModel, VariantPage
from app.services.orchestration.discovery import DiscoveryService

router = APIRouter(prefix="/datasets/{dataset_id}/discovery", tags=["Process discovery"])


def service(request: Request) -> DiscoveryService:
    return request.app.state.discovery


@router.post("", response_model=DiscoveryResult)
def discover(dataset_id: UUID, body: DiscoveryRequest, request: Request) -> dict:
    return service(request).run(str(dataset_id), body)


@router.get("", response_model=DiscoveryResult)
def result(dataset_id: UUID, request: Request) -> dict:
    return service(request).result(str(dataset_id))


@router.get("/processes/{process_id}", response_model=ProcessModel)
def process(dataset_id: UUID, process_id: str, request: Request) -> dict:
    return service(request).process(str(dataset_id), process_id)


@router.get("/processes/{process_id}/variants", response_model=VariantPage)
def variants(
    dataset_id: UUID,
    process_id: str,
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    return service(request).variants(str(dataset_id), process_id, offset, limit)
