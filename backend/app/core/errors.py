"""Consistent JSON errors with no request payload or exception internals."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas.common import ErrorBody, ErrorDetail, ErrorResponse
from app.services.ingestion.errors import DatasetError


def error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details)
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "UPLOAD_TOO_LARGE"}
        return error_response(
            exc.status_code,
            codes.get(exc.status_code, "HTTP_ERROR"),
            exc.detail if isinstance(exc.detail, str) else "The request could not be completed.",
            request.state.request_id,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(location=list(item["loc"]), message=item["msg"], type=item["type"])
            for item in exc.errors()
        ]
        return error_response(
            422,
            "VALIDATION_ERROR",
            "The request contains invalid values.",
            request.state.request_id,
            details=details,
        )

    @app.exception_handler(DatasetError)
    async def dataset_error(request: Request, exc: DatasetError) -> JSONResponse:
        return error_response(
            exc.status_code,
            exc.code,
            exc.message,
            request.state.request_id,
        )
