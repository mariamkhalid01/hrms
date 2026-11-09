"""API contracts and failure behavior, without fixture event logs or mining results."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def application() -> FastAPI:
    return create_app(Settings(_env_file=None, app_env="test"))


@pytest.fixture
def client(application: FastAPI):
    with TestClient(application) as test_client:
        yield test_client


def test_health_returns_contract(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "hr-process-mining-api",
        "version": "0.1.0",
        "environment": "test",
    }
    UUID(response.headers["x-request-id"])


def test_request_ids_are_preserved_or_replaced(client: TestClient):
    request_id = str(uuid4())
    assert client.get("/api/v1/health", headers={"X-Request-ID": request_id}).headers[
        "x-request-id"
    ] == request_id
    replaced = client.get("/api/v1/health", headers={"X-Request-ID": "not-a-uuid"})
    UUID(replaced.headers["x-request-id"])


def test_unknown_route_returns_json_error(client: TestClient):
    response = client.get("/api/v1/datasets")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Not Found",
            "request_id": response.headers["x-request-id"],
        }
    }


def test_wrong_method_returns_json_error(client: TestClient):
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_allowed_browser_origin(client: TestClient):
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_cors_preflight_and_disallowed_origin(client: TestClient):
    headers = {
        "Origin": "http://127.0.0.1:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Request-ID",
    }
    assert client.options("/api/v1/health", headers=headers).status_code == 200
    headers["Origin"] = "https://unrelated.example"
    blocked = client.options("/api/v1/health", headers=headers)
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers


def test_invalid_values_get_safe_json_details(application: FastAPI):
    @application.get("/test-only/validation")
    async def validated(count: int):
        return {"count": count}

    with TestClient(application) as client:
        response = client.get("/test-only/validation?count=private-value")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["location"] == ["query", "count"]
    assert "private-value" not in response.text


def test_unexpected_error_is_safe_and_retains_cors(application: FastAPI):
    @application.get("/test-only/failure")
    async def fails():
        raise RuntimeError("internal secret")

    with TestClient(application) as client:
        response = client.get(
            "/test-only/failure", headers={"Origin": "http://localhost:5173"}
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "internal secret" not in response.text


def test_only_implemented_routes_are_exposed(client: TestClient):
    specification = client.get("/api/openapi.json").json()
    assert set(specification["paths"]) == {
        "/api/v1/health",
        "/api/v1/datasets/config",
        "/api/v1/datasets/upload",
        "/api/v1/datasets/{dataset_id}",
        "/api/v1/datasets/{dataset_id}/validate",
        "/api/v1/datasets/{dataset_id}/process",
        "/api/v1/datasets/{dataset_id}/result",
        "/api/v1/datasets/{dataset_id}/discovery",
        "/api/v1/datasets/{dataset_id}/discovery/processes/{process_id}",
        "/api/v1/datasets/{dataset_id}/discovery/processes/{process_id}/variants",
        "/api/v1/datasets/{dataset_id}/analytics",
        "/api/v1/datasets/{dataset_id}/analytics/processes/{process_id}",
        "/api/v1/datasets/{dataset_id}/analytics/processes/{process_id}/variants",
        "/api/v1/datasets/{dataset_id}/analytics/findings",
        "/api/v1/datasets/{dataset_id}/analysis-jobs",
        "/api/v1/datasets/{dataset_id}/analysis-jobs/latest",
        "/api/v1/datasets/{dataset_id}/analysis-jobs/{job_id}",
        "/api/v1/datasets/{dataset_id}/recommendations",
        "/api/v1/datasets/{dataset_id}/cases",
        "/api/v1/datasets/{dataset_id}/cases/{case_id}",
    }


def test_startup_and_health_do_not_read_csv(monkeypatch):
    import pandas as pd

    def unexpected_read(*args, **kwargs):
        raise AssertionError("The foundation must not read any dataset on startup")

    monkeypatch.setattr(pd, "read_csv", unexpected_read)
    with TestClient(create_app(Settings(_env_file=None, app_env="test"))) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_settings_use_hr_environment_prefix(monkeypatch):
    monkeypatch.setenv("HR_APP_ENV", "production")
    monkeypatch.setenv("HR_CORS_ORIGINS", '["https://hr.example"]')
    settings = Settings(_env_file=None)
    assert settings.app_env == "production"
    assert settings.cors_origins == ["https://hr.example"]


def test_settings_reject_invalid_cors_origins():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["*"])
