"""Real ingestion-engine behavior using small in-memory records, never default data."""

import json
from pathlib import Path

import pandas as pd
import pytest

from app.services.mapping.mapper import suggest_mapping
from app.services.process_separation.separator import summarize_processes
from app.services.validation.engine import validate_and_normalize


def make_frame(**overrides):
    data = {
        "case_id": ["001", "001", "002", "002"],
        "activity": ["Submitted", "Approved", "Submitted", "Rejected"],
        "timestamp": [
            "2025-01-02T09:00:00+02:00",
            "2025-01-02T10:00:00+02:00",
            "2025-01-03T09:00:00Z",
            "2025-01-03T10:00:00Z",
        ],
        "process_type": ["Custom workflow"] * 4,
        "event_id": ["e1", "e2", "e3", "e4"],
        "event_order": ["1", "2", "1", "2"],
        "custom_flag": ["NA", "001", "", "False"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def codes(report):
    return {issue["code"] for issue in report["issues"]}


def test_generic_process_preserves_source_and_normalizes_utc():
    frame = make_frame()
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"]
    assert report["summary"]["event_count"] == 4
    assert report["summary"]["case_count"] == 2
    assert result.iloc[0]["timestamp"] == "2025-01-02T07:00:00+00:00"
    assert result.iloc[0]["case_id"] == "001"
    assert result.iloc[0]["attributes"]["custom_flag"] == "NA"
    assert result.iloc[1]["attributes"]["custom_flag"] == "001"
    assert result.iloc[0]["source_event_order"] == 1
    assert summarize_processes(result) == [
        {"name": "Custom workflow", "event_count": 4, "case_count": 2}
    ]
    json.dumps(result.to_dict("records"), allow_nan=False)


def test_renamed_columns_use_manual_mapping():
    frame = make_frame().rename(
        columns={"case_id": "ticket", "activity": "operation", "timestamp": "finished"}
    )
    mapping = suggest_mapping(frame.columns.tolist())
    mapping.update(case_id="ticket", activity="operation", timestamp="finished")
    report, result = validate_and_normalize(frame, mapping)
    assert report["valid"] and len(result) == 4
    assert "ticket" in result.iloc[0]["attributes"]


def test_no_process_column_is_a_single_generic_process():
    frame = make_frame().drop(columns="process_type")
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and "SINGLE_PROCESS_ASSUMED" in codes(report)
    assert result.process_type.unique().tolist() == ["Single process"]


def test_process_names_namespace_shared_case_ids():
    frame = make_frame(case_id=["same"] * 4, process_type=["A", "A", "B", "B"])
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and report["summary"]["case_count"] == 2
    assert "CASE_ID_SHARED_ACROSS_PROCESSES" in codes(report)
    assert result.case_key.nunique() == 2


@pytest.mark.parametrize("field", ["case_id", "activity", "timestamp"])
def test_missing_required_mapping_blocks(field):
    frame = make_frame()
    mapping = suggest_mapping(frame.columns.tolist())
    mapping[field] = None
    report, result = validate_and_normalize(frame, mapping)
    assert not report["valid"] and result is None
    assert "REQUIRED_MAPPING_MISSING" in codes(report)


def test_optional_mapping_to_unknown_source_blocks():
    frame = make_frame()
    mapping = suggest_mapping(frame.columns.tolist())
    mapping["cost"] = "missing"
    report, result = validate_and_normalize(frame, mapping)
    assert not report["valid"] and result is None
    assert "MAPPING_COLUMN_NOT_FOUND" in codes(report)


def test_missing_mapped_process_and_required_cells_block():
    frame = make_frame(
        activity=["", "Approved", "Submitted", "Rejected"], process_type=["P", "", "P", "P"]
    )
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert not report["valid"] and result is None
    errors = [item for item in report["issues"] if item["code"] == "REQUIRED_VALUE_MISSING"]
    assert {item["field"] for item in errors} == {"activity", "process_type"}
    assert errors[0]["row_numbers"] == [1]


def test_invalid_timestamp_never_drops_record():
    frame = make_frame(timestamp=["bad date", "2025-01-02", "2025-01-03", "2025-01-04"])
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert not report["valid"] and result is None
    assert report["summary"]["event_count"] == 4
    assert "INVALID_TIMESTAMP" in codes(report)


def test_start_after_end_and_outside_timestamp_block():
    frame = make_frame(
        activity_start_timestamp=["2025-01-02T11:00:00+02:00"] * 4,
        activity_end_timestamp=["2025-01-02T10:00:00+02:00"] * 4,
    )
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert not report["valid"] and result is None
    assert {"START_AFTER_END", "TIMESTAMP_OUTSIDE_INTERVAL"} <= codes(report)


def test_timestamp_inside_interval_but_not_completion_warns():
    frame = make_frame().iloc[:2].copy()
    frame["activity_end_timestamp"] = ["2025-01-02T12:00:00+02:00"] * 2
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and result is not None
    assert "TIMESTAMP_END_MISMATCH" in codes(report)


def test_same_completion_column_can_map_to_timestamp_and_end():
    frame = make_frame()
    mapping = suggest_mapping(frame.columns.tolist())
    mapping["activity_end"] = "timestamp"
    report, result = validate_and_normalize(frame, mapping)
    assert report["valid"] and (result.timestamp == result.activity_end).all()
    mapping["activity"] = "case_id"
    report, _ = validate_and_normalize(frame, mapping)
    assert not report["valid"] and "MAPPING_COLUMN_REUSED" in codes(report)


def test_exact_duplicates_warn_and_remain_in_result():
    frame = pd.concat([make_frame(), make_frame().iloc[:1]], ignore_index=True)
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and len(result) == 5
    assert {"DUPLICATE_RECORDS", "DUPLICATE_EVENT_ID"} <= codes(report)


def test_conflicting_event_id_blocks():
    frame = make_frame(event_id=["same", "same", "e3", "e4"])
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert not report["valid"] and result is None and "EVENT_ID_CONFLICT" in codes(report)


def test_equivalent_normalized_event_ids_warn_despite_different_time_representations():
    frame = make_frame().iloc[:2].copy()
    frame["activity"] = "Submitted"
    frame["event_id"] = "same"
    frame["timestamp"] = ["2025-01-02T09:00:00+02:00", "2025-01-02T07:00:00Z"]
    frame["event_order"] = ["1", "1.0"]
    frame["custom_flag"] = "unchanged"
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and len(result) == 2
    assert "DUPLICATE_EVENT_ID" in codes(report)
    assert "EVENT_ID_CONFLICT" not in codes(report)


def test_ordering_is_stable_with_explicit_order_then_source_row():
    frame = make_frame(
        case_id=["same"] * 4,
        timestamp=[
            "2025-01-02T11:00:00Z",
            "2025-01-02T10:00:00Z",
            "2025-01-02T10:00:00Z",
            "2025-01-02T10:00:00Z",
        ],
        event_order=["4", "2", "1", "2"],
    )
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and "SOURCE_SEQUENCE_DISORDER" in codes(report)
    assert result.source_row.tolist() == [3, 2, 4, 1]
    assert result.event_order.tolist() == [1, 2, 3, 4]


@pytest.mark.parametrize("value", ["-1", "0", "1.5", "abc", "999999999999999999999999"])
def test_invalid_source_order_blocks(value):
    frame = make_frame(event_order=[value, "2", "1", "2"])
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert not report["valid"] and result is None and "INVALID_EVENT_ORDER" in codes(report)


def test_chronological_rows_with_conflicting_explicit_sequence_warn():
    frame = make_frame(event_order=["2", "1", "1", "2"])
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and "EVENT_ORDER_TIME_CONFLICT" in codes(report)
    assert result.source_event_order.tolist() == [2, 1, 1, 2]
    assert result.event_order.tolist() == [1, 2, 1, 2]


@pytest.mark.parametrize(
    "timestamp,code",
    [
        ("2025-10-26 02:30:00", "DST_AMBIGUOUS_TIME"),
        ("2025-03-30 02:30:00", "DST_NONEXISTENT_TIME"),
    ],
)
def test_dst_local_time_errors(timestamp, code):
    frame = make_frame(timestamp=[timestamp] * 4)
    report, result = validate_and_normalize(
        frame, suggest_mapping(frame.columns.tolist()), timezone="Europe/Berlin"
    )
    assert not report["valid"] and result is None and code in codes(report)


def test_aware_offsets_preserve_instant_despite_selected_timezone():
    frame = make_frame(timestamp=["2025-10-26T02:30:00+02:00"] * 4)
    report, result = validate_and_normalize(
        frame, suggest_mapping(frame.columns.tolist()), timezone="Europe/Berlin"
    )
    assert report["valid"] and result.iloc[0].timestamp == "2025-10-26T00:30:00+00:00"


def test_day_first_choice_and_explicit_format():
    frame = make_frame(timestamp=["03/04/2025 10:00"] * 4)
    mapping = suggest_mapping(frame.columns.tolist())
    report, result = validate_and_normalize(frame, mapping, timezone="Africa/Cairo", day_first=True)
    assert report["valid"] and "AMBIGUOUS_DATE_ORDER" in codes(report)
    assert result.iloc[0].timestamp == "2025-04-03T08:00:00+00:00"
    report, result = validate_and_normalize(frame, mapping, timestamp_format="%d/%m/%Y %H:%M")
    assert report["valid"] and "AMBIGUOUS_DATE_ORDER" not in codes(report)


def test_optional_cost_missing_values_and_singleton_are_nonblocking():
    frame = make_frame(cost=["EGP 5", "10.50", "", "0"], resource_id=["", "r1", "r2", "r3"])
    report, result = validate_and_normalize(frame.iloc[:3], suggest_mapping(frame.columns.tolist()))
    assert report["valid"]
    assert {"NONNUMERIC_COST", "OPTIONAL_VALUE_MISSING", "SINGLE_EVENT_CASES"} <= codes(report)
    assert result.iloc[0]["cost"] is None
    assert result.iloc[0]["attributes"]["cost"] == "EGP 5"


def test_case_keys_are_collision_safe_json_tuples():
    frame = make_frame(case_id=["b::c", "b::c", "c", "c"], process_type=["a", "a", "a::b", "a::b"])
    report, result = validate_and_normalize(frame, suggest_mapping(frame.columns.tolist()))
    assert report["valid"] and result.case_key.nunique() == 2


def test_explicit_existing_combined_test_dataset_when_available():
    path = (
        Path(__file__).resolve().parents[2] / "outputs" / "synthetic_hr_dataset" / "event_log.csv"
    )
    if not path.exists():
        pytest.skip("Optional user-provided test data is not distributed with the application")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    report, result = validate_and_normalize(
        frame, suggest_mapping(frame.columns.tolist()), timezone="Africa/Cairo"
    )
    assert report["valid"]
    assert report["summary"]["event_count"] == 4700
    assert report["summary"]["case_count"] == 500
    assert report["summary"]["process_count"] == 4
    assert len(result) == 4700
    assert set(result.iloc[0]["attributes"]) == set(frame.columns)
