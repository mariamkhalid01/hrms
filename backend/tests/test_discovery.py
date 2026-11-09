"""Independent count/sequence oracles against real PM4Py, plus lifecycle/API regressions."""

import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd
import pm4py
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.schemas.discovery import DiscoveryRequest
from app.services.discovery.engine import discover
from app.services.discovery.log import build_log, prepare_frame
from app.services.discovery.serialization import graph_components
from app.services.validation.engine import validate_and_normalize


def normalize(frame):
    mapping = {
        name: name
        for name in (
            "case_id",
            "activity",
            "timestamp",
            "process_type",
            "event_order",
            "activity_start",
            "activity_end",
            "status",
        )
        if name in frame.columns
    }
    report, normalized = validate_and_normalize(frame.astype(str), mapping=mapping)
    assert report["valid"], report["issues"]
    return normalized


def events(sequences, process="Unfamiliar HR workflow", states=None):
    rows = []
    for number, sequence in enumerate(sequences):
        for index, activity in enumerate(sequence):
            rows.append(
                {
                    "case_id": f"{number:03}",
                    "activity": activity,
                    "timestamp": f"2025-01-{number + 1:02}T{index + 1:02}:00:00Z",
                    "process_type": process,
                    "case_state": states[number] if states else "NA",
                }
            )
    return pd.DataFrame(rows)


def mine(frame, options=None, **settings):
    return discover(
        normalize(frame),
        options or DiscoveryRequest(),
        Settings(_env_file=None, app_env="test", **settings),
    )


def edges(model):
    labels = {activity["id"]: activity["label"] for activity in model["activities"]}
    return {
        (labels[edge["source"]], labels[edge["target"]]): edge["frequency"]
        for edge in model["transitions"]
    }


def test_exact_counts_branches_loops_variants_and_performance():
    models, variants = mine(events(["ABBC", "AC", "ABAC"]))
    model = models[0]
    assert model["event_count"] == 10
    assert {item["label"]: item["frequency"] for item in model["activities"]} == {
        "A": 4,
        "B": 3,
        "C": 3,
    }
    assert edges(model) == {
        ("A", "B"): 2,
        ("B", "B"): 1,
        ("B", "C"): 1,
        ("A", "C"): 2,
        ("B", "A"): 1,
    }
    assert model["metadata"]["repeated_case_count"] == 2
    assert len(model["alternative_paths"]) == 2
    assert len(model["loops"]) == 1
    assert sum(item["frequency"] for item in model["start_activities"]) == 3
    assert sum(item["frequency"] for item in model["end_activities"]) == 3
    rows = variants[model["id"]]
    assert {tuple(row["activity_sequence"]) for row in rows} == {
        tuple("ABBC"),
        tuple("AC"),
        tuple("ABAC"),
    }
    assert sum(row["percentage"] for row in rows) == pytest.approx(100)
    assert sorted(row["average_case_duration_seconds"] for row in rows) == [3600, 10800, 10800]
    assert all(row["completed_duration_seconds"]["count"] == 0 for row in rows)
    assert all(edge["elapsed_time_seconds"]["mean"] == 3600 for edge in model["transitions"])
    assert all(edge["inter_activity_gap_seconds"]["count"] == 0 for edge in model["transitions"])
    assert model["inductive"]["status"] == "discovered"
    assert {node["id"] for node in model["react_flow"]["nodes"]} == {
        item["id"] for item in model["activities"]
    }
    json.dumps({"models": models, "variants": variants}, allow_nan=False)


def test_petri_arcs_markings_and_visible_labels_are_valid():
    models, _ = mine(events(["ABC", "ADC", "ABC"]))
    net = models[0]["inductive"]["petri_net"]
    places = {item["id"] for item in net["places"]}
    transitions = {item["id"] for item in net["transitions"]}
    assert sum(item["initial_tokens"] for item in net["places"]) == 1
    assert sum(item["final_tokens"] for item in net["places"]) == 1
    assert {item["label"] for item in net["transitions"] if not item["silent"]} == set("ABCD")
    assert all(
        (arc["source"] in places and arc["target"] in transitions)
        or (arc["source"] in transitions and arc["target"] in places)
        for arc in net["arcs"]
    )
    assert all(arc["weight"] > 0 for arc in net["arcs"])


def test_inductive_zero_noise_replays_training_log():
    frame = prepare_frame(normalize(events(["ABBC", "AC", "ABAC"])), DiscoveryRequest())
    log, _ = build_log(frame, DiscoveryRequest())
    net, initial, final = pm4py.convert_to_petri_net(pm4py.discover_process_tree_inductive(log))
    fitness = pm4py.fitness_token_based_replay(log, net, initial, final)
    assert fitness["log_fitness"] == pytest.approx(1)


def test_unknown_processes_and_reused_case_ids_stay_independent():
    frame = pd.concat(
        [events(["AB", "AB"], "Relocation"), events(["XY", "XZ"], "Visa renewal")],
        ignore_index=True,
    )
    models, variants = mine(frame)
    assert {model["name"] for model in models} == {"Relocation", "Visa renewal"}
    assert sum(model["case_count"] for model in models) == 4
    assert edges(models[0]) == {("A", "B"): 2}
    assert len(variants[models[1]["id"]]) == 2
    assert not (
        {node["id"] for node in models[0]["activities"]}
        & {node["id"] for node in models[1]["activities"]}
    )


def test_missing_process_type_uses_one_process_and_singletons_are_supported():
    frame = events(["A", "B"]).drop(columns="process_type")
    models, variants = mine(frame)
    assert models[0]["name"] == "Single process"
    assert models[0]["transitions"] == []
    assert models[0]["inductive"]["status"] == "skipped"
    assert all(row["average_case_duration_seconds"] == 0 for row in variants[models[0]["id"]])


def test_ties_respect_explicit_order_and_normalized_input_can_be_shuffled():
    source = events(["BAC"])
    source["timestamp"] = "2025-01-01T00:00:00Z"
    source["event_order"] = [2, 1, 3]
    normalized = normalize(source)
    a = discover(normalized, DiscoveryRequest(algorithm="dfg"), Settings(_env_file=None))
    b = discover(
        normalized.sample(frac=1, random_state=42),
        DiscoveryRequest(algorithm="dfg"),
        Settings(_env_file=None),
    )
    assert a == b
    assert next(iter(a[1].values()))[0]["activity_sequence"] == list("ABC")


def test_duplicate_events_are_retained_as_observed_self_loop():
    frame = events(["AB"])
    frame = pd.concat([frame.iloc[[0]], frame], ignore_index=True)
    models, _ = mine(frame)
    assert edges(models[0]) == {("A", "A"): 1, ("A", "B"): 1}


def test_case_states_preserve_censored_variants_but_exclude_them_from_induction():
    frame = events(["AB", "AC", "A", "AX"], states=["Done", "Done", "Open", "Stopped"])
    options = DiscoveryRequest(
        case_status_attribute="case_state",
        case_status_values={"Done": "completed", "Open": "incomplete", "Stopped": "cancelled"},
    )
    models, variants = mine(frame, options)
    model = models[0]
    assert model["metadata"]["case_status_counts"] == {
        "completed": 2,
        "incomplete": 1,
        "cancelled": 1,
        "unknown": 0,
    }
    assert model["inductive"]["input_case_count"] == 2
    assert model["inductive"]["excluded_case_count"] == 2
    assert ("A", "X") in edges(model)
    assert "X" not in {item["label"] for item in model["inductive"]["petri_net"]["transitions"]}
    assert sum(row["case_count"] for row in variants[model["id"]]) == 4
    assert sum(row["completed_duration_seconds"]["count"] for row in variants[model["id"]]) == 2


def test_conflicting_or_unrecognized_case_states_are_unknown():
    frame = events(["AB", "AB"], states=["Done", "Unexpected"])
    frame.loc[1, "case_state"] = "Open"
    models, _ = mine(
        frame,
        DiscoveryRequest(
            case_status_attribute="case_state",
            case_status_values={"Done": "completed", "Open": "incomplete"},
        ),
    )
    metadata = models[0]["metadata"]
    assert metadata["case_status_counts"]["unknown"] == 2
    assert metadata["conflicting_status_case_count"] == 1
    assert metadata["unrecognized_status_case_count"] == 1


def test_event_status_does_not_claim_case_completion():
    frame = events(["AB", "AB"])
    frame["status"] = "Completed"
    models, _ = mine(frame)
    assert models[0]["metadata"]["case_status_counts"]["unknown"] == 2


@pytest.mark.parametrize("setting", [{"inductive_max_events": 3}, {"inductive_max_activities": 1}])
def test_induction_limits_preserve_exact_dfg_and_variants(setting):
    models, variants = mine(events(["AB", "AB"]), **setting)
    assert models[0]["inductive"]["status"] == "skipped"
    assert "limit" in models[0]["inductive"]["reason"]
    assert edges(models[0]) == {("A", "B"): 2}
    assert variants[models[0]["id"]][0]["case_count"] == 2


def test_single_case_auto_skips_but_explicit_induction_works():
    assert mine(events(["AB"]))[0][0]["inductive"]["status"] == "skipped"
    models, _ = mine(events(["AB"]), DiscoveryRequest(algorithm="inductive"))
    assert models[0]["inductive"]["status"] == "discovered"


def test_optional_induction_failure_is_explicit_and_preserves_real_results(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("test failure")

    monkeypatch.setattr(pm4py, "discover_process_tree_inductive", fail)
    models, variants = mine(events(["AB", "AB"]))
    assert models[0]["inductive"]["status"] == "failed"
    assert models[0]["inductive"]["petri_net"] is None
    assert edges(models[0]) == {("A", "B"): 2}
    assert len(variants[models[0]["id"]]) == 1


def test_signed_interval_gaps_and_service_time():
    frame = events(["AB"])
    frame["activity_start"] = ["2025-01-01T00:00:00Z", "2025-01-01T00:30:00Z"]
    frame["activity_end"] = frame["timestamp"]
    models, _ = mine(frame)
    model = models[0]
    assert model["transitions"][0]["inter_activity_gap_seconds"]["mean"] == -1800
    assert model["transitions"][0]["overlap_count"] == 1
    assert [item["service_time_seconds"]["mean"] for item in model["activities"]] == [3600, 5400]


def test_graph_cycles_do_not_imply_within_case_repetition():
    models, _ = mine(events(["AB", "BA"]))
    assert models[0]["loops"]
    assert models[0]["metadata"]["repeated_case_count"] == 0
    assert graph_components(list("ABCD"), [("A", "B"), ("B", "A"), ("B", "C")]) == [
        ["A", "B"],
        ["C"],
        ["D"],
    ]


@pytest.fixture(scope="module")
def hr_fixture():
    path = Path(
        os.environ.get(
            "HR_TEST_EVENT_LOG",
            Path(__file__).resolve().parents[2] / "outputs/synthetic_hr_dataset/event_log.csv",
        )
    )
    if not path.is_file():
        pytest.skip("Set HR_TEST_EVENT_LOG to the separately supplied development CSV.")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame = frame.rename(
        columns={
            "activity_start_timestamp": "activity_start",
            "activity_end_timestamp": "activity_end",
        }
    )
    return frame


def test_supplied_hr_fixture_counts_sequences_and_four_independent_models(hr_fixture):
    models, variants = mine(hr_fixture)
    assert {model["name"] for model in models} == {
        "Recruitment",
        "Onboarding",
        "Leave Management",
        "Payroll",
    }
    assert sum(model["event_count"] for model in models) == 4700
    assert sum(model["case_count"] for model in models) == 500
    for model in models:
        source = hr_fixture[hr_fixture.process_type == model["name"]].copy()
        source["_instant"] = pd.to_datetime(source.timestamp, utc=True)
        source["_order"] = source.event_order.astype(int)
        source = source.sort_values(["case_id", "_instant", "_order"], kind="stable")
        sequences = source.groupby("case_id").activity.apply(tuple)
        expected_edges = Counter(
            pair for sequence in sequences for pair in zip(sequence, sequence[1:], strict=False)
        )
        assert edges(model) == expected_edges
        assert {item["label"]: item["frequency"] for item in model["activities"]} == Counter(
            source.activity
        )
        assert {
            tuple(row["activity_sequence"]): row["case_count"] for row in variants[model["id"]]
        } == Counter(sequences)
        assert model["inductive"]["status"] == "discovered"
        assert sum(row["percentage"] for row in variants[model["id"]]) == pytest.approx(100)


def test_discovery_ignores_synthetic_delay_rework_exception_flags(hr_fixture):
    options = DiscoveryRequest(algorithm="dfg")
    original = mine(hr_fixture, options)
    changed = hr_fixture.copy()
    for column in [name for name in changed if "flag" in name or "reason" in name]:
        changed[column] = "changed irrelevant attribute"
    assert mine(changed, options) == original


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(_env_file=None, app_env="test", dataset_storage_dir=tmp_path))
    with TestClient(app) as instance:
        yield instance


def prepared(client, frame=None):
    frame = events(["ABC", "ADC"]) if frame is None else frame
    uploaded = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("events.csv", frame.to_csv(index=False).encode(), "text/csv")},
    )
    assert uploaded.status_code == 201
    identifier = uploaded.json()["id"]
    mapping = {
        name: name for name in ("case_id", "activity", "timestamp", "process_type") if name in frame
    }
    validation = client.post(f"/api/v1/datasets/{identifier}/validate", json={"mapping": mapping})
    assert validation.status_code == 200 and validation.json()["valid"]
    response = client.post(
        f"/api/v1/datasets/{identifier}/process",
        json={"validation_id": validation.json()["validation_id"], "acknowledge_warnings": True},
    )
    assert response.status_code == 200
    return identifier, mapping


def test_full_api_discovery_cache_pagination_and_restart(client):
    identifier, _ = prepared(client)
    path = f"/api/v1/datasets/{identifier}/discovery"
    assert client.get(path).status_code == 404
    response = client.post(path, json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["pm4py_version"] == pm4py.__version__
    assert client.get(path).json() == result
    assert client.post(path, json={}).json() == result
    process = result["processes"][0]
    process_path = path + f"/processes/{process['id']}"
    assert client.get(process_path).json() == process
    page = client.get(process_path + "/variants?limit=1&offset=1").json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["analysis_id"] == result["analysis_id"]
    assert client.get(process_path + "/variants?offset=200").json()["items"] == []
    assert client.get(process_path + "/variants?limit=201").status_code == 422
    assert client.get(path + "/processes/no-such-process").status_code == 404
    restarted = create_app(client.app.state.settings)
    with TestClient(restarted) as other:
        assert other.get(path).json() == result


def test_remapping_invalidates_mining_and_reprocessing_requires_new_discovery(client):
    identifier, mapping = prepared(client)
    path = f"/api/v1/datasets/{identifier}"
    first = client.post(path + "/discovery", json={}).json()
    validation = client.post(path + "/validate", json={"mapping": mapping}).json()
    assert client.get(path + "/discovery").status_code == 409
    client.post(
        path + "/process",
        json={"validation_id": validation["validation_id"], "acknowledge_warnings": True},
    )
    stale = client.get(path + "/discovery")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_DISCOVERY"
    second = client.post(path + "/discovery", json={}).json()
    assert second["analysis_id"] != first["analysis_id"]
    assert second["processes"][0]["activities"] == first["processes"][0]["activities"]


@pytest.mark.parametrize("filename", ["source.csv", "normalized.jsonl"])
def test_modified_artifact_cannot_serve_stale_mining(client, filename):
    identifier, _ = prepared(client)
    path = f"/api/v1/datasets/{identifier}/discovery"
    assert client.post(path, json={}).status_code == 200
    artifact = client.app.state.datasets.store.path(identifier) / filename
    with artifact.open("a", encoding="utf-8") as output:
        output.write("\n")
    assert client.get(path).status_code == 409
    assert client.post(path, json={}).status_code == 409


def test_discovery_busy_and_input_errors_are_actionable(client):
    identifier, _ = prepared(client)
    path = f"/api/v1/datasets/{identifier}/discovery"
    assert client.post(path, json={"algorithm": "imaginary"}).status_code == 422
    assert (
        client.post(
            path,
            json={"case_status_attribute": "missing", "case_status_values": {"done": "completed"}},
        ).status_code
        == 422
    )
    assert client.app.state.discovery.capacity.acquire(blocking=False)
    try:
        assert client.post(path, json={}).status_code == 429
    finally:
        client.app.state.discovery.capacity.release()
    assert client.post(path, json={}).status_code == 200


def test_uploaded_but_unconfirmed_log_cannot_be_mined(client):
    uploaded = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("events.csv", events(["AB"]).to_csv(index=False).encode())},
    ).json()
    result = client.post(f"/api/v1/datasets/{uploaded['id']}/discovery", json={})
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "DATASET_NOT_READY"


@pytest.mark.parametrize(
    "options",
    [
        {"case_status_attribute": "state"},
        {"case_status_values": {"done": "completed"}},
        {"algorithm": "dfg", "noise_threshold": 0.2},
        {"noise_threshold": 1},
        {
            "case_status_attribute": "state",
            "case_status_values": {"Done": "completed", "done": "unknown"},
        },
    ],
)
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValidationError):
        DiscoveryRequest(**options)
