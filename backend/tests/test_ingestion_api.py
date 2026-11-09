"""Real upload-to-persistence contracts with temporary local storage."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

CSV = (
    "case_id,activity,timestamp,process_type,note\n"
    "001,Submitted,2025-01-01T09:00:00Z,Custom HR,NA\n"
    "001,Approved,2025-01-01T10:00:00Z,Custom HR,keep me\n"
)
MAPPING = {
    "case_id": "case_id",
    "activity": "activity",
    "timestamp": "timestamp",
    "process_type": "process_type",
}


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    return tmp_path / "datasets"


@pytest.fixture
def client(data_root: Path):
    app = create_app(Settings(_env_file=None, app_env="test", dataset_storage_dir=data_root))
    with TestClient(app) as instance:
        yield instance


def upload(client: TestClient, source: str = CSV) -> dict:
    response = client.post(
        "/api/v1/datasets/upload", files={"file": ("events.csv", source.encode())}
    )
    assert response.status_code == 201, response.text
    return response.json()


def validate(client: TestClient, identifier: str, mapping: dict | None = None) -> dict:
    response = client.post(
        f"/api/v1/datasets/{identifier}/validate",
        json={"mapping": mapping or MAPPING},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_config_and_startup_are_empty(client: TestClient, data_root: Path):
    assert client.get("/api/v1/datasets/config").json() == {
        "max_upload_bytes": 52_428_800,
        "max_rows": 250_000,
        "max_columns": 200,
        "preview_rows": 20,
    }
    assert not data_root.exists()


def test_upload_preserves_strings_and_full_stats(client: TestClient, data_root: Path):
    source = "case_id,activity,timestamp,note\n" + "".join(
        f"{i:03},Step,2025-01-01T09:00:00Z,{'' if i == 29 else 'NA'}\n" for i in range(30)
    )
    preview = upload(client, source)
    assert preview["row_count"] == 30
    assert len(preview["preview"]) == 20
    assert preview["preview"][0]["values"]["case_id"] == "000"
    assert preview["preview"][0]["values"]["note"] == "NA"
    note = next(c for c in preview["columns"] if c["name"] == "note")
    assert note["missing_count"] == 1
    assert note["unique_count"] == 1
    assert (data_root / preview["id"] / "source.csv").read_text() == source
    assert client.get(f"/api/v1/datasets/{preview['id']}").json() == preview


@pytest.mark.parametrize(
    ("filename", "content", "status", "code"),
    [
        ("events.txt", b"x", 400, "INVALID_FILE_EXTENSION"),
        ("events.csv", b"", 400, "EMPTY_CSV"),
        ("events.csv", b"a,b\n", 400, "EMPTY_CSV"),
        ("events.csv", b"a,a\n1,2\n", 400, "DUPLICATE_HEADERS"),
        ("events.csv", b"a,\n1,2\n", 400, "INVALID_HEADERS"),
        ("events.csv", b"a,b\n1,2,3\n", 400, "MALFORMED_CSV"),
        ("events.csv", b'a,b\n1,"unfinished\n', 400, "MALFORMED_CSV"),
        ("events.csv", b"a,b\n1,\xff\n", 415, "UNSUPPORTED_ENCODING"),
        ("events.csv", b"a,b\n1,\x00\n", 400, "BINARY_FILE"),
    ],
)
def test_invalid_upload_is_clear_and_cleaned(client, data_root, filename, content, status, code):
    response = client.post("/api/v1/datasets/upload", files={"file": (filename, content)})
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert not data_root.exists() or list(data_root.iterdir()) == []


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_supported_bom_and_delimiter(client: TestClient, encoding: str):
    response = client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                "events.CSV",
                "case_id;activity;timestamp\n001;Start;2025-01-01\n".encode(encoding),
            ),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["delimiter"] == ";"
    assert response.json()["encoding"] == encoding


def test_filename_cannot_choose_storage_path(client: TestClient, data_root: Path):
    response = client.post("/api/v1/datasets/upload", files={"file": ("../../escape.csv", CSV)})
    assert response.status_code == 201
    preview = response.json()
    assert preview["filename"] == "escape.csv"
    assert (data_root / preview["id"] / "source.csv").is_file()
    assert not (data_root.parent / "escape.csv").exists()


@pytest.mark.parametrize(
    ("overrides", "source", "code"),
    [
        ({"max_upload_bytes": 20}, CSV, "UPLOAD_TOO_LARGE"),
        ({"max_rows": 1}, CSV, "TOO_MANY_ROWS"),
        ({"max_columns": 2}, CSV, "TOO_MANY_COLUMNS"),
    ],
)
def test_exact_limits(data_root: Path, overrides: dict, source: str, code: str):
    app = create_app(Settings(_env_file=None, dataset_storage_dir=data_root, **overrides))
    with TestClient(app) as client:
        response = client.post("/api/v1/datasets/upload", files={"file": ("events.csv", source)})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == code
    assert not data_root.exists() or list(data_root.iterdir()) == []


def test_request_limit_checks_actual_stream_without_content_length(data_root: Path):
    app = create_app(Settings(_env_file=None, dataset_storage_dir=data_root, max_upload_bytes=100))
    content = iter([b"x" * 70_000])
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/datasets/upload",
            content=content,
            headers={"Content-Type": "multipart/form-data; boundary=test-boundary"},
        )
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert not data_root.exists()


def test_validate_process_persists_canonical_and_original(client, data_root):
    preview = upload(client)
    identifier = preview["id"]
    report = validate(client, identifier)
    assert report["valid"]
    response = client.post(
        f"/api/v1/datasets/{identifier}/process",
        json={
            "validation_id": report["validation_id"],
            "acknowledge_warnings": True,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert (result["event_count"], result["case_count"], result["process_count"]) == (2, 1, 1)
    assert result["processes"] == [{"name": "Custom HR", "event_count": 2, "case_count": 1}]
    assert result["status"] == "ready"
    stored = [
        json.loads(line)
        for line in (data_root / identifier / "normalized.jsonl").read_text().splitlines()
    ]
    assert stored[0]["case_id"] == "001"
    assert stored[0]["attributes"]["note"] == "NA"
    assert (data_root / identifier / "source.csv").read_text() == CSV
    assert client.get(f"/api/v1/datasets/{identifier}/result").json() == result
    second = client.post(
        f"/api/v1/datasets/{identifier}/process", json={"validation_id": report["validation_id"]}
    )
    assert second.json() == result
    assert client.get(f"/api/v1/datasets/{identifier}").json()["status"] == "ready"


def test_latest_validation_and_blocking_errors_enforced(client: TestClient):
    identifier = upload(client)["id"]
    first = validate(client, identifier)
    second = validate(client, identifier, {"case_id": "case_id", "activity": "activity"})
    assert not second["valid"]
    stale = client.post(
        f"/api/v1/datasets/{identifier}/process", json={"validation_id": first["validation_id"]}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_VALIDATION"
    blocked = client.post(
        f"/api/v1/datasets/{identifier}/process", json={"validation_id": second["validation_id"]}
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "VALIDATION_FAILED"


def test_warning_acknowledgment_is_required(client: TestClient):
    identifier = upload(client, CSV + CSV.splitlines()[-1] + "\n")["id"]
    report = validate(client, identifier)
    assert report["valid"] and report["summary"]["warning_count"] > 0
    response = client.post(
        f"/api/v1/datasets/{identifier}/process", json={"validation_id": report["validation_id"]}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WARNINGS_NOT_ACKNOWLEDGED"


def test_source_tampering_rejected(client: TestClient, data_root: Path):
    identifier = upload(client)["id"]
    report = validate(client, identifier)
    (data_root / identifier / "source.csv").write_text(CSV + "changed")
    response = client.post(
        f"/api/v1/datasets/{identifier}/process",
        json={
            "validation_id": report["validation_id"],
            "acknowledge_warnings": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_CHANGED"


def test_persistence_survives_app_restart(client: TestClient, data_root: Path):
    preview = upload(client)
    report = validate(client, preview["id"])
    restarted = create_app(Settings(_env_file=None, dataset_storage_dir=data_root))
    with TestClient(restarted) as second:
        assert second.get(f"/api/v1/datasets/{preview['id']}").json()["status"] == "validated"
        response = second.post(
            f"/api/v1/datasets/{preview['id']}/process",
            json={
                "validation_id": report["validation_id"],
                "acknowledge_warnings": True,
            },
        )
        assert response.status_code == 200


def test_concurrent_processing_is_idempotent(client: TestClient):
    identifier = upload(client)["id"]
    report = validate(client, identifier)

    def process():
        return client.post(
            f"/api/v1/datasets/{identifier}/process",
            json={
                "validation_id": report["validation_id"],
                "acknowledge_warnings": True,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: process(), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json() == responses[1].json()


def test_unknown_not_ready_and_missing_validation(client: TestClient):
    assert client.get(f"/api/v1/datasets/{uuid4()}").status_code == 404
    identifier = upload(client)["id"]
    assert client.get(f"/api/v1/datasets/{identifier}/result").status_code == 409
    response = client.post(
        f"/api/v1/datasets/{identifier}/process", json={"validation_id": str(uuid4())}
    )
    assert response.json()["error"]["code"] == "VALIDATION_REQUIRED"


def test_malformed_mapping_contract_is_422(client: TestClient):
    identifier = upload(client)["id"]
    response = client.post(f"/api/v1/datasets/{identifier}/validate", json={"mapping": "not-a-map"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
