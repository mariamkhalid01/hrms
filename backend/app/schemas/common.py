"""Small, stable contracts shared with the frontend API client."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["hr-process-mining-api"] = "hr-process-mining-api"
    version: str
    environment: Literal["development", "test", "production"]


class ErrorDetail(BaseModel):
    location: list[str | int]
    message: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
