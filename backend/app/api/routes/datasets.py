"""Upload and preparation routes. CPU and filesystem work runs in worker threads."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Request, UploadFile

from app.schemas.datasets import (
    DatasetPreview,
    MappingRequest,
    ProcessRequest,
    ReadyDataset,
    UploadConfig,
    ValidationReport,
)
from app.services.orchestration.datasets import DatasetService

router = APIRouter(prefix="/datasets", tags=["Datasets"])


def service(request: Request) -> DatasetService:
    return request.app.state.datasets


@router.get("/config", response_model=UploadConfig)
def config(request: Request) -> UploadConfig:
    settings = request.app.state.settings
    return UploadConfig(
        max_upload_bytes=settings.max_upload_bytes,
        max_rows=settings.max_rows,
        max_columns=settings.max_columns,
        preview_rows=settings.preview_rows,
    )


@router.post("/upload", response_model=DatasetPreview, status_code=201)
def upload(request: Request, file: Annotated[UploadFile, File()]) -> dict:
    return service(request).upload(file.filename, file.file)


@router.get("/{dataset_id}", response_model=DatasetPreview)
def preview(dataset_id: UUID, request: Request) -> dict:
    return service(request).preview(str(dataset_id))


@router.post("/{dataset_id}/validate", response_model=ValidationReport)
def validate(dataset_id: UUID, body: MappingRequest, request: Request) -> dict:
    return service(request).validate(str(dataset_id), body)


@router.post("/{dataset_id}/process", response_model=ReadyDataset)
def process(dataset_id: UUID, body: ProcessRequest, request: Request) -> dict:
    return service(request).process(str(dataset_id), body)


@router.get("/{dataset_id}/result", response_model=ReadyDataset)
def result(dataset_id: UUID, request: Request) -> dict:
    return service(request).result(str(dataset_id))
