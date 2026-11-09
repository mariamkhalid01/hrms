"""Explicit live-HTTP check; supply the external development fixture with --dataset."""

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


def analyze(client, frame, filename):
    upload = request(
        client,
        "POST",
        "/datasets/upload",
        files={"file": (filename, frame.to_csv(index=False).encode(), "text/csv")},
    )
    path = f"/datasets/{upload['id']}"
    report = request(
        client,
        "POST",
        path + "/validate",
        json={"mapping": upload["suggested_mapping"], "timezone": "Africa/Cairo"},
    )
    check(report["valid"], "Validation must pass")
    request(
        client,
        "POST",
        path + "/process",
        json={"validation_id": report["validation_id"], "acknowledge_warnings": True},
    )
    result = request(client, "POST", path + "/discovery", json={})
    check(result == request(client, "GET", path + "/discovery"), "Persisted result differs")
    for model in result["processes"]:
        group = (
            frame[frame.process_type == model["name"]].copy()
            if "process_type" in frame
            else frame.copy()
        )
        group["_timestamp"] = pd.to_datetime(group.timestamp, utc=True)
        group["_order"] = group.event_order.astype(int)
        ordered = group.sort_values(["case_id", "_timestamp", "_order"], kind="stable")
        sequences, durations = [], {}
        for _, case in ordered.groupby("case_id"):
            sequence = tuple(case.activity)
            sequences.append(sequence)
            duration = (case._timestamp.iloc[-1] - case._timestamp.iloc[0]).total_seconds()
            durations.setdefault(sequence, []).append(duration)
        check(model["event_count"] == len(group), "Event count")
        check(model["case_count"] == len(sequences), "Case count")
        check(
            {item["label"]: item["frequency"] for item in model["activities"]}
            == Counter(group.activity),
            "Activity frequencies",
        )
        labels = {item["id"]: item["label"] for item in model["activities"]}
        expected = Counter(
            pair for sequence in sequences for pair in zip(sequence, sequence[1:], strict=False)
        )
        observed = {
            (labels[edge["source"]], labels[edge["target"]]): edge["frequency"]
            for edge in model["transitions"]
        }
        check(observed == expected, "DFG frequencies")
        variants, offset = [], 0
        while True:
            page = request(
                client,
                "GET",
                path + f"/discovery/processes/{model['id']}/variants",
                params={"offset": offset, "limit": 10},
            )
            variants.extend(page["items"])
            offset += len(page["items"])
            if offset >= page["total"]:
                break
        check(
            {tuple(item["activity_sequence"]): item["case_count"] for item in variants}
            == Counter(sequences),
            "Variant sequences/frequencies",
        )
        for item in variants:
            samples = durations[tuple(item["activity_sequence"])]
            check(item["average_case_duration_seconds"] == mean(samples), "Variant mean duration")
            check(
                item["median_case_duration_seconds"] == median(samples), "Variant median duration"
            )
        check(model["inductive"]["status"] == "discovered", "Real Inductive Miner result")
    return result


with httpx.Client(base_url=args.base_url, timeout=180) as client:
    check(request(client, "GET", "/health")["status"] == "ok", "Live health")
    combined = analyze(client, source, "combined_discovery_test.csv")
    check(
        {model["name"] for model in combined["processes"]}
        == {"Recruitment", "Onboarding", "Leave Management", "Payroll"},
        "Four fixture categories",
    )
    single = source[source.process_type == source.process_type.iloc[0]].copy()
    standalone = analyze(client, single.drop(columns="process_type"), "single_discovery_test.csv")
    check(standalone["process_count"] == 1, "No process field works")
    single["process_type"] = "Unseen custom workflow"
    custom = analyze(client, single, "custom_discovery_test.csv")
    check(custom["processes"][0]["name"] == "Unseen custom workflow", "Unknown process works")

check(args.dataset.read_bytes() == original, "Original fixture unchanged")
summary = {
    "checks_passed": checks,
    "base_url": args.base_url,
    "fixture_sha256": hashlib.sha256(original).hexdigest(),
    "combined_analysis_id": combined["analysis_id"],
    "duration_ms": combined["duration_ms"],
    "processes": [
        {key: model[key] for key in ("name", "event_count", "case_count", "variant_count")}
        for model in combined["processes"]
    ],
}
if args.report:
    args.report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
