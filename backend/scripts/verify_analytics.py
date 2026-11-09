"""Opt-in live integration check using an existing external event log; never rewrites it."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

import httpx
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--base-url", default="http://127.0.0.1:5173/api/v1")
parser.add_argument("--report", type=Path)
args = parser.parse_args()
original = args.dataset.read_bytes()
source = pd.read_csv(args.dataset, dtype=str, keep_default_na=False)
checks = 0


def check(condition, message):
    global checks
    if not condition:
        raise AssertionError(message)
    checks += 1


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    check(response.is_success, f"{method} {path}: {response.status_code}: {response.text[:400]}")
    return response.json()


with httpx.Client(base_url=args.base_url, timeout=180) as client:
    check(request(client, "GET", "/health")["status"] == "ok", "Healthy API")
    upload = request(
        client,
        "POST",
        "/datasets/upload",
        files={"file": ("analytics_fixture_test.csv", original, "text/csv")},
    )
    path = f"/datasets/{upload['id']}"
    validation = request(
        client,
        "POST",
        path + "/validate",
        json={"mapping": upload["suggested_mapping"], "timezone": "Africa/Cairo"},
    )
    check(validation["valid"], "Fixture validation")
    request(
        client,
        "POST",
        path + "/process",
        json={"validation_id": validation["validation_id"], "acknowledge_warnings": True},
    )
    result = request(client, "POST", path + "/analytics", json={})
    check(result == request(client, "GET", path + "/analytics"), "Saved metrics")
    check(result == request(client, "POST", path + "/analytics", json={}), "Cache identity")
    discovery = request(client, "GET", path + "/discovery")
    check(discovery["analysis_id"] == result["discovery_analysis_id"], "Bound to actual discovery")
    check(result["total_events"] == len(source), "Dataset event count")
    check(
        result["total_cases"] == source.groupby(["process_type", "case_id"]).ngroups, "Case count"
    )
    for process in result["processes"]:
        group = source[source.process_type == process["name"]].copy()
        group["time"] = pd.to_datetime(group.timestamp, utc=True)
        group["start"] = pd.to_datetime(group.activity_start_timestamp, utc=True)
        group["end"] = pd.to_datetime(group.activity_end_timestamp, utc=True)
        group["order"] = group.event_order.astype(int)
        group = group.sort_values(["case_id", "time", "order"], kind="stable")
        spans, gaps = [], []
        for _, case in group.groupby("case_id"):
            spans.append((case.time.iloc[-1] - case.time.iloc[0]).total_seconds())
            records = list(case.itertuples())
            gaps.extend(
                (right.start - left.end).total_seconds()
                for left, right in zip(records, records[1:], strict=False)
                if right.start >= left.end
            )
        for key, expected in (
            ("mean", mean(spans)),
            ("median", median(spans)),
            ("minimum", min(spans)),
            ("maximum", max(spans)),
        ):
            check(process["case_duration_seconds"][key] == expected, "Case duration " + key)
        check(
            process["processing_seconds"]["mean"]
            == mean((group.end - group.start).dt.total_seconds()),
            "Measured processing mean",
        )
        check(
            process["waiting"]["measured_wait_seconds"]["median"] == median(gaps),
            "Measured waiting median",
        )
        check(process["waiting"]["approximation_count"] == 0, "Full interval coverage")
        check(
            process["completion"]["completion_rate_percentage"] is None,
            "No invented completion rate",
        )
        check(
            {item["label"]: item["event_count"] for item in process["resources"]["members"]}
            == Counter(group.resource_id),
            "Resource workload counts",
        )
        check(
            {item["label"]: item["event_count"] for item in process["departments"]["members"]}
            == Counter(group.department_id),
            "Department workload counts",
        )
        page = request(
            client, "GET", path + f"/analytics/processes/{process['id']}/variants?limit=200"
        )
        check(
            sum(item["case_count"] for item in page["items"]) == process["total_cases"],
            "Variant cases",
        )
        check(
            {item["id"] for item in process["activities"]}
            == {
                item["id"]
                for model in discovery["processes"]
                if model["id"] == process["id"]
                for item in model["activities"]
            },
            "Map-compatible activity IDs",
        )
    findings, offset = [], 0
    while True:
        page = request(
            client, "GET", path + "/analytics/findings", params={"offset": offset, "limit": 20}
        )
        findings.extend(page["items"])
        offset += len(page["items"])
        if offset >= page["total"]:
            break
    check(len(findings) == result["finding_count"], "Finding pagination")
    for item in findings:
        check(
            item["observed_value"] > item["baseline"]["threshold"], "Finding exceeds its threshold"
        )
        check(item["affected_case_count"] >= 2, "Minimum case support")
        check(item["cause_status"] == "not_established", "No invented cause")
        check(item["potential_impact"]["savings_estimated"] is False, "No invented savings")
        for sample in item["evidence"]["examples"]:
            rows = source.iloc[[row - 1 for row in sample["source_rows"]]]
            check(set(rows.case_id) == {sample["case_id"]}, "Evidence case refers to actual rows")
            check(
                set(rows.process_type) == {item["process_type"]}, "Evidence belongs to same process"
            )
    # Explicit derivative upload tests estimation without altering the provided fixture.
    subset = source[source.process_type == source.process_type.iloc[0]].drop(
        columns=[
            "process_type",
            "activity_start_timestamp",
            "activity_end_timestamp",
            "resource_id",
            "department_id",
        ]
    )
    test_upload = request(
        client,
        "POST",
        "/datasets/upload",
        files={
            "file": (
                "analytics_estimation_test.csv",
                subset.to_csv(index=False).encode(),
                "text/csv",
            )
        },
    )
    test_path = f"/datasets/{test_upload['id']}"
    report = request(
        client, "POST", test_path + "/validate", json={"mapping": test_upload["suggested_mapping"]}
    )
    request(
        client,
        "POST",
        test_path + "/process",
        json={"validation_id": report["validation_id"], "acknowledge_warnings": True},
    )
    approximate = request(client, "POST", test_path + "/analytics", json={})["processes"][0]
    check(approximate["waiting"]["approximation_count"] > 0, "Waiting estimates available")
    check(
        approximate["waiting"]["measured_wait_seconds"]["mean"] is None, "No false measured waiting"
    )
    check(approximate["processing_seconds"]["mean"] is None, "No fabricated processing time")
    check(
        approximate["resources"] is None and approximate["departments"] is None,
        "Absent assignment data omitted",
    )

check(args.dataset.read_bytes() == original, "Original fixture unchanged")
summary = {
    "checks_passed": checks,
    "base_url": args.base_url,
    "dataset_id": upload["id"],
    "analytics_id": result["analysis_id"],
    "duration_ms": result["duration_ms"],
    "fixture_sha256": hashlib.sha256(original).hexdigest(),
    "processes": [
        {
            "name": process["name"],
            "cases": process["total_cases"],
            "events": process["total_events"],
            "findings": process["finding_count"],
        }
        for process in result["processes"]
    ],
    "finding_categories": dict(Counter(item["category"] for item in findings)),
}
if args.report:
    args.report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
