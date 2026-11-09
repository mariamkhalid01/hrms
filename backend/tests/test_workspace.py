"""Background stages, current evidence recommendations, and real case timeline contracts."""

import json
from threading import Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

CSV = (
    "case_id,activity,timestamp,process_type,note\n"
    "001,A,2025-01-01T00:00:00Z,Custom,original\n"
    "001,B,2025-01-01T01:00:00Z,Custom,keep me\n"
    "001,A,2025-01-01T03:00:00Z,Custom,repeat\n"
    "002,A,2025-01-02T00:00:00Z,Custom,other\n"
    "002,B,2025-01-02T01:00:00Z,Custom,other\n"
    "002,A,2025-01-02T05:00:00Z,Custom,repeat\n"
)


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(Settings(_env_file=None, app_env="test", dataset_storage_dir=tmp_path))
    ) as instance:
        yield instance


def validated(client, source=CSV):
    upload = client.post("/api/v1/datasets/upload", files={"file": ("events.csv", source.encode())})
    assert upload.status_code == 201
    path = f"/api/v1/datasets/{upload.json()['id']}"
    report = client.post(
        path + "/validate",
        json={
            "mapping": {key: key for key in ("case_id", "activity", "timestamp", "process_type")}
        },
    ).json()
    assert report["valid"]
    return path, report["validation_id"]


def finish(client, path, validation_id):
    started = client.post(
        path + "/analysis-jobs", json={"validation_id": validation_id, "acknowledge_warnings": True}
    )
    assert started.status_code == 202, started.text
    identifier = started.json()["id"]
    deadline = monotonic() + 15
    while monotonic() < deadline:
        response = client.get(path + "/analysis-jobs/" + identifier)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] in {"completed", "failed"}:
            return result
        sleep(0.01)
    raise AssertionError("Job did not complete")


def test_real_job_runs_complete_pipeline_and_stages(client):
    path, revision = validated(client)
    job = finish(client, path, revision)
    assert job["status"] == "completed", job
    assert len(job["stages"]) == 8
    assert all(stage["status"] == "completed" for stage in job["stages"])
    assert all(stage["started_at"] <= stage["completed_at"] for stage in job["stages"])
    assert all(
        left["completed_at"] <= right["started_at"]
        for left, right in zip(job["stages"], job["stages"][1:], strict=False)
    )
    assert "percent" not in json.dumps(job)
    assert client.get(path + "/analysis-jobs/latest").json() == job
    assert client.get(path + "/result").json()["event_count"] == 6
    analytics = client.get(path + "/analytics").json()
    assert analytics["analysis_id"] == job["analytics_analysis_id"]
    assert analytics["case_duration_seconds"]["mean"] == 14400
    assert analytics["case_duration_seconds"]["median"] == 14400
    assert client.get(path + "/discovery").json()["analysis_id"] == job["discovery_analysis_id"]


def test_progress_polling_does_not_block_on_computation_and_duplicate_start_reuses_job(
    client, monkeypatch
):
    path, revision = validated(client)
    entered, release = Event(), Event()
    original = client.app.state.datasets._source

    def held(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(client.app.state.datasets, "_source", held)
    try:
        job = client.post(
            path + "/analysis-jobs", json={"validation_id": revision, "acknowledge_warnings": True}
        ).json()
        assert entered.wait(5)
        running = client.get(path + "/analysis-jobs/latest").json()
        assert running["status"] == "running" and running["current_stage"] == "reading_dataset"
        duplicate = client.post(path + "/analysis-jobs", json={}).json()
        assert duplicate["id"] == job["id"]
        assert running["stages"][1]["status"] == "pending"
    finally:
        release.set()


def test_callbacks_reflect_actual_normalization_analytics_and_detection(client, monkeypatch):
    import app.services.analytics.engine as analytics
    import app.services.bottlenecks.engine as bottlenecks
    import app.services.recommendations.engine as recommendations
    import app.services.validation.engine as validation

    path, revision = validated(client)
    identifier = path.rsplit("/", 1)[1]
    observed = []

    def instrument(module, name, stage):
        original = getattr(module, name)

        def wrapped(*args, **kwargs):
            job = client.app.state.jobs.latest(identifier)
            assert job["current_stage"] == stage
            observed.append(stage)
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, wrapped)

    instrument(validation, "normalize_events", "normalizing_data")
    instrument(analytics, "process_metrics", "calculating_performance_metrics")
    instrument(bottlenecks, "detect", "detecting_bottlenecks")
    instrument(recommendations, "recommend", "preparing_recommendations")
    assert finish(client, path, revision)["status"] == "completed"
    assert observed == [
        "normalizing_data",
        "calculating_performance_metrics",
        "detecting_bottlenecks",
        "preparing_recommendations",
    ]


def test_job_rejects_unconfirmed_warnings_and_stale_revision(client):
    path, revision = validated(client, CSV + CSV.splitlines()[-1] + "\n")
    assert client.post(path + "/analysis-jobs", json={"validation_id": revision}).status_code == 409
    assert (
        client.post(
            path + "/analysis-jobs", json={"validation_id": "stale", "acknowledge_warnings": True}
        ).status_code
        == 409
    )


def test_failed_source_check_does_not_complete_unrun_stages(client):
    path, revision = validated(client)
    identifier = path.rsplit("/", 1)[1]
    source = client.app.state.datasets.store.path(identifier) / "source.csv"
    source.write_bytes(source.read_bytes() + b"\n")
    job = finish(client, path, revision)
    assert job["status"] == "failed" and job["error"]["code"] == "SOURCE_CHANGED"
    assert job["stages"][0]["status"] == "failed"
    assert all(stage["status"] == "pending" for stage in job["stages"][1:])


def test_case_pages_keep_source_attributes_and_match_real_variant_sequences(client):
    path, revision = validated(client)
    assert finish(client, path, revision)["status"] == "completed"
    page = client.get(path + "/cases?limit=1").json()
    assert page["total"] == 2 and len(page["items"]) == 1
    case = page["items"][0]
    assert case["case_id"] == "001" and case["event_count"] == 3
    assert case["status"] == "unknown"
    detail = client.get(path + f"/cases/{case['id']}?offset=1&limit=2").json()
    assert [item["activity"] for item in detail["events"]] == ["B", "A"]
    assert detail["events"][0]["attributes"]["note"] == "keep me"
    assert detail["events"][0]["source_row"] == 2
    assert client.get(path + "/cases?search=002").json()["total"] == 1
    assert (
        client.get(path + "/cases", params={"variant_id": case["variant_id"]}).json()["total"] == 2
    )
    assert client.get(path + "/cases?process_id=wrong").status_code == 404
    assert client.get(path + "/cases/missing").status_code == 404
    assert client.get(path + "/cases?limit=201").status_code == 422


def test_recommendations_link_only_existing_findings_without_invented_improvements(client):
    path, revision = validated(client)
    assert finish(client, path, revision)["status"] == "completed"
    findings = client.get(path + "/analytics/findings").json()
    recommendations = client.get(path + "/recommendations").json()
    ids = {item["id"] for item in findings["items"]}
    assert recommendations["total"] == len(ids) == 2
    assert recommendations["analysis_id"] == findings["analysis_id"]
    for item in recommendations["items"]:
        assert set(item["finding_ids"]) <= ids
        assert item["expected_improvement"] is None and item["actions"]
        assert item["measurement_plan"] and item["affected_case_count"] == 2
    assert client.get(path + "/recommendations?offset=100").json()["items"] == []


def test_restart_marks_an_unfinished_saved_job_failed(client):
    from uuid import uuid4

    from app.schemas.workspace import AnalysisJob, JobStage
    from app.services.orchestration.datasets import now

    path, _ = validated(client)
    dataset_id = path.rsplit("/", 1)[1]
    job_id = str(uuid4())
    job = AnalysisJob(
        id=job_id,
        dataset_id=dataset_id,
        status="running",
        current_stage="reading_dataset",
        created_at=now(),
        updated_at=now(),
        stages=[JobStage(key="reading_dataset", label="Reading dataset", status="running")],
    )
    client.app.state.datasets.store.write(dataset_id, f"job-{job_id}.json", job.model_dump())
    result = client.get(path + "/analysis-jobs/" + job_id).json()
    assert result["status"] == "failed" and result["error"]["code"] == "ANALYSIS_INTERRUPTED"
