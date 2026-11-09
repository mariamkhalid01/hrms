"""Independent arithmetic and evidence checks against normalized logs and real discovery."""

import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean, median

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.schemas.analytics import AnalyticsRequest, Thresholds
from app.schemas.discovery import DiscoveryRequest
from app.services.analytics.engine import analyze, effective_thresholds
from app.services.bottlenecks.engine import baseline
from app.services.discovery.engine import discover
from app.services.ingestion.errors import DatasetError
from app.services.mapping.mapper import CANONICAL_FIELDS
from app.services.validation.engine import validate_and_normalize


def source(sequences, durations=None, waits=None, intervals=True):
    rows = []
    for index, sequence in enumerate(sequences):
        instant = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index)
        for order, label in enumerate(sequence):
            gap = waits[index][order] if waits is not None else 20
            duration = durations[index][order] if durations is not None else 10
            start = instant + timedelta(seconds=gap)
            instant = start + timedelta(seconds=duration)
            row = {
                "case_id": f"c{index:03}",
                "process_type": "Custom process",
                "activity": label,
                "timestamp": instant.isoformat(),
                "event_order": str(order + 1),
            }
            if intervals:
                row.update(activity_start=start.isoformat(), activity_end=instant.isoformat())
            rows.append(row)
    return pd.DataFrame(rows)


def normalized(frame):
    mapping = {name: name for name in CANONICAL_FIELDS if name in frame}
    report, canonical = validate_and_normalize(frame.fillna(""), mapping=mapping)
    assert report["valid"], report["issues"]
    return canonical


def performance(frame, options=None, discovery_options=None):
    options = options or AnalyticsRequest()
    discovery_options = discovery_options or DiscoveryRequest(algorithm="dfg")
    canonical = normalized(frame)
    models, variants = discover(canonical, discovery_options, Settings(_env_file=None))
    return analyze(
        canonical,
        {
            "processes": models,
            "variants": variants,
            "configuration": discovery_options.model_dump(),
        },
        options,
    )


def test_exact_processing_wait_case_duration_and_variant_statistics():
    frame = source(["AB", "AB"], durations=[[10, 30], [20, 40]], waits=[[0, 100], [0, 200]])
    processes, variants, findings = performance(frame)
    process = processes[0]
    assert (process["total_cases"], process["total_events"]) == (2, 4)
    assert process["case_duration_seconds"] == {
        "count": 2,
        "mean": 185,
        "median": 185,
        "minimum": 130,
        "maximum": 240,
    }
    assert process["full_interval_case_duration_seconds"]["mean"] == 200
    assert process["processing_seconds"]["mean"] == 25
    assert process["waiting"]["measured_wait_seconds"]["mean"] == 150
    assert process["waiting"]["approximate_wait_seconds"]["mean"] is None
    assert [item["processing_seconds"]["median"] for item in process["activities"]] == [15, 35]
    assert process["activities"][1]["incoming_wait"]["measured_wait_seconds"]["median"] == 150
    assert process["transitions"][0]["frequency"] == 2
    assert variants[process["id"]][0]["case_duration_seconds"]["mean"] == 185
    assert variants[process["id"]][0]["percentage"] == 100
    assert process["resources"] is None and process["departments"] is None
    assert process["transitions"][0]["resource_handovers"] is None
    assert process["transitions"][0]["department_handovers"] is None
    assert findings == []
    json.dumps(processes, allow_nan=False)


def test_missing_intervals_are_labeled_estimates_never_processing_time():
    frame = source(["AB"] * 5, intervals=False)
    options = AnalyticsRequest(thresholds=Thresholds(waiting_seconds=5))
    processes, _, findings = performance(frame, options)
    process = processes[0]
    assert process["processing_seconds"]["count"] == 0
    assert process["processing_seconds"]["mean"] is None
    assert process["waiting"]["measured_wait_seconds"]["count"] == 0
    assert process["waiting"]["approximate_wait_seconds"]["mean"] == 30
    assert process["waiting"]["approximation_count"] == 5
    assert len(findings) == 1
    assert findings[0]["measurement"] == "approximation"
    assert findings[0]["severity"] == "medium"
    assert findings[0]["category"] == "long_waiting"


def test_partial_intervals_are_separate_and_overlaps_are_not_negative_waiting():
    frame = source(["AB", "AB", "AB"])
    frame.loc[3, "activity_start"] = ""
    previous_end = pd.Timestamp(frame.loc[4, "activity_end"])
    frame.loc[5, "activity_start"] = (previous_end - timedelta(seconds=5)).isoformat()
    process = performance(frame)[0][0]
    wait = process["waiting"]
    assert wait["interval_pair_count"] == 2
    assert wait["approximation_count"] == 1
    assert wait["overlap_count"] == 1
    assert wait["measured_wait_seconds"]["count"] == 1
    assert wait["measured_wait_seconds"]["mean"] == 20
    assert wait["approximate_wait_seconds"]["mean"] == 30
    assert wait["signed_interval_gap_seconds"]["minimum"] == -5
    assert process["processing_seconds"]["count"] == 5


def test_completion_identification_and_partial_coverage():
    frame = source(["AB"] * 4)
    frame["case_status"] = ["Done", "Done", "Open", "Open", "Cancelled", "Cancelled", "?", "?"]
    frame["status"] = "Completed"
    assert performance(frame)[0][0]["completion"]["completion_rate_percentage"] is None
    config = DiscoveryRequest(
        algorithm="dfg",
        case_status_attribute="case_status",
        case_status_values={"Done": "completed", "Open": "incomplete", "Cancelled": "cancelled"},
    )
    metrics = performance(frame, discovery_options=config)[0][0]
    assert metrics["completion"]["status_coverage_percentage"] == 75
    assert metrics["completion"]["known_status_completion_rate_percentage"] == pytest.approx(
        100 / 3
    )
    assert metrics["completion"]["completion_rate_percentage"] is None
    frame.loc[6:, "case_status"] = "Done"
    metrics = performance(frame, discovery_options=config)[0][0]
    assert metrics["completion"]["completion_rate_percentage"] == 50
    assert metrics["completed_case_duration_seconds"]["count"] == 2


def test_resource_department_counts_missing_ids_and_repeated_assignments():
    frame = source(["ABA", "AB"])
    frame["resource_id"] = ["r1", "r2", "r1", "r1", ""]
    frame["department"] = ["d1", "d2", "d1", "d1", "d1"]
    process = performance(frame)[0][0]
    resources = process["resources"]
    assert resources["known_event_count"] == 4 and resources["missing_event_count"] == 1
    assert resources["comparable_adjacent_pairs"] == 2
    assert resources["changed_assignment_pairs"] == 2
    assert resources["handover_rate_percentage"] == 100
    assert resources["fully_observed_case_count"] == 1
    one = next(item for item in resources["members"] if item["label"] == "r1")
    assert one["case_count"] == 2 and one["event_count"] == 3
    assert one["repeated_case_assignments"] == 1 and one["same_activity_repeat_assignments"] == 1
    assert one["event_share_percentage"] == 75 and one["total_processing_seconds"] == 30
    assert process["departments"]["changed_assignment_pairs"] == 2
    assert process["departments"]["same_assignment_pairs"] == 1
    assert sum(edge["resource_handovers"] for edge in process["transitions"]) == 2


def test_resource_name_fallback_and_unavailable_work_is_not_zero():
    frame = source(["AB"], intervals=False)
    frame["resource_name"] = ["Person A", "Person B"]
    process = performance(frame)[0][0]
    assert process["resources"]["field"] == "resource_name"
    assert all(item["total_processing_seconds"] is None for item in process["resources"]["members"])


def test_robust_baseline_and_business_override():
    config = Thresholds()
    values = [10] * 18 + [100, 100]
    reference = baseline(values, config, "test")
    assert reference["comparison_value"] == 10
    assert reference["threshold"] == 20
    assert baseline(values[:2], config, "test") is None
    assert baseline(values[:2], config, "test", 5)["threshold"] == 5


def test_processing_outliers_have_real_evidence_and_affected_case_counts():
    frame = source(["AB"] * 20, durations=[[value, 10] for value in [10] * 18 + [100, 100]])
    _, _, findings = performance(frame)
    match = next(item for item in findings if item["category"] == "long_processing")
    assert match["entity"]["label"] == "A"
    assert match["observed_value"] == 100 and match["baseline"]["threshold"] == 20
    assert match["affected_case_count"] == 2 and match["severity"] == "high"
    assert match["potential_impact"]["observed_excess_seconds"] == 160
    assert match["potential_impact"]["savings_estimated"] is False
    assert match["cause_status"] == "not_established"
    assert {item["case_id"] for item in match["evidence"]["examples"]} == {"c018", "c019"}


def test_persistently_slow_activity_is_compared_to_process_peer_means():
    frame = source(["ABCDEF"] * 5, durations=[[10, 10, 10, 10, 10, 100]] * 5)
    findings = performance(frame)[2]
    match = next(item for item in findings if item["category"] == "long_processing")
    assert match["entity"]["label"] == "F"
    assert "entity means" in match["baseline"]["cohort"]
    assert match["affected_case_count"] == 5


def test_waiting_delayed_cases_and_slow_variant_use_observed_timings():
    sequences = ["AB"] * 18 + ["AC"] * 2
    waits = [[0, value] for value in [10] * 18 + [1000, 1000]]
    options = AnalyticsRequest(thresholds=Thresholds(waiting_seconds=50))
    _, _, findings = performance(source(sequences, waits=waits), options)
    categories = {item["category"] for item in findings}
    assert {"long_waiting", "delayed_cases", "slow_variant"} <= categories
    assert all(item["affected_case_count"] == 2 for item in findings)
    assert (
        next(item for item in findings if item["category"] == "long_waiting")["observed_value"]
        == 1000
    )


def test_repeated_work_uses_case_sequences_not_activity_popularity():
    _, _, findings = performance(source(["ABA"] * 3 + ["AB"] * 2))
    repeat = next(item for item in findings if item["category"] == "repeated_activity")
    assert repeat["observed_value"] == 60 and repeat["affected_case_count"] == 3
    assert repeat["evidence"]["examples"][0]["unit"] == "count"
    assert any(item["category"] == "rework_path" for item in findings)
    assert performance(source(["AB"] * 30))[2] == []


def test_handover_rule_requires_comparable_observations():
    frame = source(["ABC"] * 5)
    frame["resource_id"] = ["r1", "r2", "r3"] * 5
    options = AnalyticsRequest(thresholds=Thresholds(handovers_per_case=1))
    findings = performance(frame, options)[2]
    match = next(item for item in findings if item["category"] == "frequent_handovers")
    assert match["observed_value"] == 2 and match["affected_case_count"] == 5
    frame.loc[frame.activity == "B", "resource_id"] = ""
    assert not any(
        item["category"] == "frequent_handovers" for item in performance(frame, options)[2]
    )


def test_workload_imbalance_requires_measured_time_and_role_cohorts():
    frame = source(["AB"] * 10, durations=[[value, value] for value in [10] * 8 + [100, 100]])
    frame["resource_id"] = [f"r{index // 4}" for index in range(len(frame))]
    frame["resource_role"] = "Analyst"
    findings = performance(frame)[2]
    matches = [item for item in findings if item["category"] == "workload_imbalance"]
    assert len(matches) == 1 and matches[0]["entity"]["label"] == "r4"
    assert matches[0]["observed_value"] == 400
    frame.loc[frame.resource_id == "r4", "resource_role"] = "Specialist"
    assert not any(item["category"] == "workload_imbalance" for item in performance(frame)[2])
    frame = frame.drop(columns=["activity_start", "activity_end"])
    assert not any(item["category"] == "workload_imbalance" for item in performance(frame)[2])


def test_process_specific_thresholds_are_inherited_and_round_trip_without_reset():
    options = AnalyticsRequest(
        thresholds=Thresholds(processing_seconds=70, minimum_samples=8),
        process_overrides={"Custom process": Thresholds(waiting_seconds=100)},
    )
    restored = AnalyticsRequest.model_validate(options.model_dump())
    thresholds = effective_thresholds(restored, "Custom process")
    assert thresholds.processing_seconds == 70 and thresholds.minimum_samples == 8
    assert thresholds.waiting_seconds == 100
    assert options.model_dump()["process_overrides"]["Custom process"] == {"waiting_seconds": 100}


def test_processes_with_different_duration_baselines_are_not_compared():
    slow = source(["AB"] * 8, durations=[[100, 100]] * 8)
    slow["process_type"] = "Other process"
    fast = source(["AB"] * 8)
    metrics, _, findings = performance(pd.concat([fast, slow], ignore_index=True))
    assert len(metrics) == 2 and sum(item["total_cases"] for item in metrics) == 16
    assert findings == []


def test_singletons_have_observed_zero_span_but_no_waiting_evidence():
    frame = source(["A"]).drop(columns="process_type")
    process = performance(frame)[0][0]
    assert process["name"] == "Single process"
    assert process["case_duration_seconds"]["mean"] == 0
    assert process["full_interval_case_duration_seconds"]["mean"] == 10
    assert process["waiting"]["approximate_wait_seconds"]["mean"] is None
    assert process["waiting"]["measured_wait_seconds"]["mean"] is None


def test_unknown_override_targets_are_rejected():
    with pytest.raises(DatasetError, match="unknown process"):
        performance(source(["AB"]), AnalyticsRequest(process_overrides={"missing": Thresholds()}))
    with pytest.raises(DatasetError, match="does not exist"):
        performance(
            source(["AB"]),
            AnalyticsRequest(thresholds=Thresholds(processing_seconds_by_activity={"absent": 5})),
        )


@pytest.mark.parametrize(
    "options",
    [
        {"iqr_multiplier": 0},
        {"minimum_samples": 2},
        {"waiting_seconds": -1},
        {"waiting_seconds": float("inf")},
        {"processing_seconds_by_activity": {"A": float("nan")}},
        {"repeated_case_percentage": 101},
        {"unknown_setting": True},
    ],
)
def test_invalid_thresholds_are_rejected(options):
    with pytest.raises(ValidationError):
        Thresholds(**options)


@pytest.fixture(scope="module")
def hr_source():
    path = Path(
        os.environ.get(
            "HR_TEST_EVENT_LOG",
            Path(__file__).resolve().parents[2] / "outputs/synthetic_hr_dataset/event_log.csv",
        )
    )
    if not path.is_file():
        pytest.skip("Supply the existing fixture via HR_TEST_EVENT_LOG.")
    return pd.read_csv(path, dtype=str, keep_default_na=False).rename(
        columns={
            "activity_start_timestamp": "activity_start",
            "activity_end_timestamp": "activity_end",
            "department_id": "department",
        }
    )


def test_hr_fixture_timings_counts_and_resources_match_independent_calculations(hr_source):
    metrics, variants, findings = performance(hr_source)
    assert sum(item["total_cases"] for item in metrics) == 500
    assert sum(item["total_events"] for item in metrics) == 4700
    assert len(metrics) == 4
    for process in metrics:
        group = hr_source[hr_source.process_type == process["name"]].copy()
        group["time"] = pd.to_datetime(group.timestamp, utc=True)
        group["start"] = pd.to_datetime(group.activity_start, utc=True)
        group["end"] = pd.to_datetime(group.activity_end, utc=True)
        group["order"] = group.event_order.astype(int)
        spans, waits = [], []
        group = group.sort_values(["case_id", "time", "order"], kind="stable")
        for _, case in group.groupby("case_id"):
            spans.append((case.time.iloc[-1] - case.time.iloc[0]).total_seconds())
            waits.extend(
                (right.start - left.end).total_seconds()
                for left, right in zip(
                    list(case.itertuples()), list(case.itertuples())[1:], strict=False
                )
                if right.start >= left.end
            )
        assert process["case_duration_seconds"]["mean"] == mean(spans)
        assert process["case_duration_seconds"]["median"] == median(spans)
        assert process["waiting"]["measured_wait_seconds"]["mean"] == mean(waits)
        assert process["processing_seconds"]["mean"] == mean(
            (group.end - group.start).dt.total_seconds()
        )
        assert {
            item["label"]: item["event_count"] for item in process["resources"]["members"]
        } == Counter(group.resource_id)
        assert process["completion"]["completion_rate_percentage"] is None
        assert sum(item["case_count"] for item in variants[process["id"]]) == process["total_cases"]
    assert all(item["cause_status"] == "not_established" for item in findings)
    assert all(item["observed_value"] > item["baseline"]["threshold"] for item in findings)


def test_synthetic_flags_and_precomputed_duration_columns_do_not_drive_analytics(hr_source):
    first = performance(hr_source)
    changed = hr_source.copy()
    for name in (
        "delay_flag",
        "rework_flag",
        "exception_flag",
        "handoff_flag",
        "processing_minutes",
        "waiting_business_minutes",
        "delay_threshold_business_minutes",
        "delay_reason",
    ):
        changed[name] = "irrelevant"
    assert performance(changed) == first


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(_env_file=None, app_env="test", dataset_storage_dir=tmp_path))
    with TestClient(app) as instance:
        yield instance


def ready(client):
    frame = source(["ABA"] * 5)
    result = client.post(
        "/api/v1/datasets/upload", files={"file": ("test.csv", frame.to_csv(index=False).encode())}
    )
    assert result.status_code == 201
    identifier = result.json()["id"]
    path = f"/api/v1/datasets/{identifier}"
    mapping = {key: key for key in CANONICAL_FIELDS if key in frame}
    report = client.post(path + "/validate", json={"mapping": mapping}).json()
    assert report["valid"]
    assert (
        client.post(
            path + "/process",
            json={"validation_id": report["validation_id"], "acknowledge_warnings": True},
        ).status_code
        == 200
    )
    return path, mapping


def test_api_automatically_uses_real_discovery_and_supports_cache_filters_pages_restart(client):
    path, _ = ready(client)
    response = client.post(path + "/analytics", json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert client.get(path + "/analytics").json() == result
    assert client.post(path + "/analytics", json={}).json() == result
    assert client.get(path + "/discovery").json()["analysis_id"] == result["discovery_analysis_id"]
    process = result["processes"][0]
    assert client.get(path + f"/analytics/processes/{process['id']}").json() == process
    page = client.get(path + "/analytics/findings?limit=1").json()
    assert page["total"] == 2 and len(page["items"]) == 1
    filtered = client.get(
        path + "/analytics/findings",
        params={"process_id": process["id"], "category": "repeated_activity"},
    ).json()
    assert filtered["total"] == 1
    assert client.get(path + "/analytics/findings?limit=201").status_code == 422
    assert client.get(path + "/analytics/findings?category=invented").status_code == 422
    variants = client.get(path + f"/analytics/processes/{process['id']}/variants").json()
    assert variants["total"] == 1 and variants["items"][0]["case_count"] == 5
    assert client.get(path + "/analytics/processes/missing").status_code == 404
    with TestClient(create_app(client.app.state.settings)) as restarted:
        assert restarted.get(path + "/analytics").json() == result


def test_discovery_changes_invalidate_analytics_and_new_thresholds_recompute(client):
    path, _ = ready(client)
    first = client.post(path + "/analytics", json={}).json()
    assert client.post(path + "/discovery", json={"algorithm": "dfg"}).status_code == 200
    stale = client.get(path + "/analytics")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_ANALYTICS"
    second = client.post(
        path + "/analytics", json={"thresholds": {"repeated_case_percentage": 100}}
    ).json()
    assert second["analysis_id"] != first["analysis_id"]
    assert second["finding_count"] == 1


def test_mapping_or_normalized_file_change_prevents_stale_metrics(client):
    path, mapping = ready(client)
    assert client.post(path + "/analytics", json={}).status_code == 200
    identifier = path.rsplit("/", 1)[1]
    normalized_path = client.app.state.datasets.store.path(identifier) / "normalized.jsonl"
    original = normalized_path.read_bytes()
    normalized_path.write_bytes(original + b"\n")
    assert client.get(path + "/analytics").status_code == 409
    normalized_path.write_bytes(original)
    client.post(path + "/validate", json={"mapping": mapping})
    assert client.get(path + "/analytics").status_code == 409


def test_analytics_busy_and_override_errors_recover_cleanly(client):
    path, _ = ready(client)
    assert client.post(path + "/discovery", json={}).status_code == 200
    assert client.app.state.discovery.capacity.acquire(blocking=False)
    try:
        response = client.post(path + "/analytics", json={})
        assert response.status_code == 429 and response.json()["error"]["code"] == "ANALYTICS_BUSY"
    finally:
        client.app.state.discovery.capacity.release()
    assert (
        client.post(path + "/analytics", json={"process_overrides": {"missing": {}}}).status_code
        == 422
    )
    assert client.post(path + "/analytics", json={}).status_code == 200
