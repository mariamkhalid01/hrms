"""Read-only, independent CSV-versus-API checks; never imports mining engine code."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from urllib.parse import urlencode
from urllib.request import urlopen


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc) if value else None


def dist(values):
    return {"count": len(values), "mean": mean(values) if values else None,
            "median": median(values) if values else None, "minimum": min(values) if values else None,
            "maximum": max(values) if values else None}


def verify(dataset_id, source_folder, base_url="http://127.0.0.1:8000/api/v1"):
    source_folder = Path(source_folder)
    source = source_folder / "event_log.csv"
    initial_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with source.open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    checks = 0

    def check(condition, description):
        nonlocal checks
        if not condition:
            raise AssertionError(description)
        checks += 1

    def numeric(actual, expected, description):
        check((actual is None and expected is None) or
              (actual is not None and expected is not None and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-6)), description)

    def distribution(actual, values, description):
        for key, expected in dist(values).items():
            numeric(actual[key], expected, f"{description}.{key}")

    prefix = f"{base_url.rstrip('/')}/datasets/{dataset_id}"

    def get(path):
        with urlopen(prefix + path, timeout=180) as response:
            check(response.status == 200, "GET " + path)
            return json.load(response)

    def pages(path):
        output = []
        offset = 0
        while True:
            page = get(path + ("&" if "?" in path else "?") + urlencode({"offset": offset, "limit": 200}))
            output.extend(page["items"])
            offset += len(page["items"])
            if offset >= page["total"]:
                check(len(output) == page["total"], "Pagination totals " + path)
                return output
            check(bool(page["items"]), "Pagination advances " + path)

    discovery, analytics = get("/discovery"), get("/analytics")
    check(discovery["analysis_id"] == analytics["discovery_analysis_id"], "Same discovery revision")
    check(discovery["dataset_id"] == analytics["dataset_id"] == dataset_id, "Same requested dataset")
    check(len(records) == discovery["event_count"] == analytics["total_events"], "Total events")
    groups = defaultdict(list)
    for index, row in enumerate(records, 1):
        row["_source_row"] = index
        row["_timestamp"] = instant(row["timestamp"])
        row["_start"] = instant(row.get("activity_start_timestamp", row.get("activity_start", "")))
        row["_end"] = instant(row.get("activity_end_timestamp", row.get("activity_end", "")))
        row["_processing"] = (row["_end"] - row["_start"]).total_seconds() if row["_start"] and row["_end"] else None
        groups[(row.get("process_type", "Single process"), row["case_id"])].append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: (row["_timestamp"], float(row.get("event_order") or row["_source_row"]), row["_source_row"]))
    check(len(groups) == discovery["case_count"] == analytics["total_cases"], "Total cases")
    check(len({key[0] for key in groups}) == discovery["process_count"] == analytics["process_count"], "Process partitions")

    options = discovery["configuration"]
    status_attribute = options.get("case_status_attribute")
    status_mapping = {key.strip().casefold(): value for key, value in options.get("case_status_values", {}).items()}

    def state(rows):
        values = {row.get(status_attribute, "").strip().casefold() for row in rows if status_attribute and row.get(status_attribute, "")}
        interpreted = {status_mapping.get(value, "unknown") for value in values}
        return next(iter(interpreted)) if len(interpreted) == 1 else "unknown"

    all_spans = [(rows[-1]["_timestamp"] - rows[0]["_timestamp"]).total_seconds() for rows in groups.values()]
    distribution(analytics["case_duration_seconds"], all_spans, "Overall pooled case span")
    process_summaries, source_context = [], {}
    for model in discovery["processes"]:
        name, identifier = model["name"], model["id"]
        process = next(item for item in analytics["processes"] if item["id"] == identifier)
        cases = {key[1]: rows for key, rows in groups.items() if key[0] == name}
        events = [row for rows in cases.values() for row in rows]
        activity_records, edge_records, variants = defaultdict(list), defaultdict(list), defaultdict(list)
        beginnings, endings, repetitions, spans, intervals = Counter(), Counter(), Counter(), [], []
        statuses = Counter(state(rows) for rows in cases.values())
        for case_id, rows in cases.items():
            sequence = tuple(row["activity"] for row in rows)
            variants[sequence].append(rows)
            beginnings[sequence[0]] += 1
            endings[sequence[-1]] += 1
            repetitions.update({activity: 1 for activity, frequency in Counter(sequence).items() if frequency > 1})
            spans.append((rows[-1]["_timestamp"] - rows[0]["_timestamp"]).total_seconds())
            if all(row["_processing"] is not None for row in rows):
                intervals.append((max(row["_end"] for row in rows) - min(row["_start"] for row in rows)).total_seconds())
            for row in rows:
                activity_records[row["activity"]].append(row)
            for left, right in zip(rows, rows[1:]):
                edge_records[(left["activity"], right["activity"])].append((left, right))
        check(model["case_count"] == process["total_cases"] == len(cases), name + " case count")
        check(model["event_count"] == process["total_events"] == len(events), name + " event count")
        check(model["variant_count"] == process["variant_count"] == len(variants), name + " variant count")
        distribution(process["case_duration_seconds"], spans, name + " case spans")
        distribution(process["full_interval_case_duration_seconds"], intervals, name + " full intervals")
        distribution(process["completed_case_duration_seconds"], [(rows[-1]["_timestamp"] - rows[0]["_timestamp"]).total_seconds() for rows in cases.values() if state(rows) == "completed"], name + " completed spans")
        distribution(process["processing_seconds"], [row["_processing"] for row in events if row["_processing"] is not None], name + " processing")
        for key in ("completed", "incomplete", "cancelled", "unknown"):
            check(process["completion"]["status_counts"][key] == statuses[key], name + " status " + key)
        numeric(process["completion"]["completion_rate_percentage"], None if statuses["unknown"] else 100 * statuses["completed"] / len(cases), name + " completion rate")
        repeated_cases = sum(len({row["activity"] for row in rows}) < len(rows) for rows in cases.values())
        check(process["repeated_case_count"] == repeated_cases, name + " repeated cases")
        labels = {item["id"]: item["label"] for item in model["activities"]}
        check(set(labels.values()) == set(activity_records), name + " activities are actual labels")
        for activity in model["activities"]:
            label = activity["label"]
            rows = activity_records[label]
            check(activity["frequency"] == len(rows), name + " event frequency " + label)
            check(activity["case_frequency"] == len({row["case_id"] for row in rows}), name + " case frequency " + label)
            check(activity["repeated_case_count"] == repetitions[label], name + " repeated frequency " + label)
            check(activity["start_frequency"] == beginnings[label] and activity["end_frequency"] == endings[label], name + " observed boundaries " + label)
            distribution(activity["service_time_seconds"], [row["_processing"] for row in rows if row["_processing"] is not None], name + " processing " + label)
        check(len(model["transitions"]) == len(edge_records), name + " exact DFG edge count")
        all_gaps, all_estimates = [], []
        for edge in model["transitions"]:
            key = labels[edge["source"]], labels[edge["target"]]
            pairs = edge_records[key]
            check(edge["frequency"] == len(pairs), name + " transition frequency " + str(key))
            check(edge["case_frequency"] == len({left["case_id"] for left, _ in pairs}), name + " transition case frequency " + str(key))
            check(edge["is_self_loop"] == (key[0] == key[1]), name + " direct loop " + str(key))
            elapsed = [(right["_timestamp"] - left["_timestamp"]).total_seconds() for left, right in pairs]
            gaps = [(right["_start"] - left["_end"]).total_seconds() for left, right in pairs if right["_start"] and left["_end"]]
            estimates = [(right["_timestamp"] - left["_timestamp"]).total_seconds() for left, right in pairs if not(right["_start"] and left["_end"])]
            all_gaps.extend(gaps)
            all_estimates.extend(estimates)
            distribution(edge["elapsed_time_seconds"], elapsed, name + " edge elapsed " + str(key))
            measured = next(item for item in process["transitions"] if item["id"] == edge["id"])["waiting"]
            distribution(measured["measured_wait_seconds"], [value for value in gaps if value >= 0], name + " edge measured wait " + str(key))
            distribution(measured["approximate_wait_seconds"], estimates, name + " edge approximate wait " + str(key))
            check(measured["overlap_count"] == sum(value < 0 for value in gaps), name + " edge overlaps " + str(key))
        distribution(process["waiting"]["measured_wait_seconds"], [value for value in all_gaps if value >= 0], name + " pooled waiting")
        distribution(process["waiting"]["approximate_wait_seconds"], all_estimates, name + " pooled approximation")
        check(process["waiting"]["overlap_count"] == sum(value < 0 for value in all_gaps), name + " pooled overlaps")
        exported_variants = pages(f"/analytics/processes/{identifier}/variants")
        check(len(exported_variants) == len(variants), name + " paginated variants")
        for variant in exported_variants:
            rows_list = variants[tuple(variant["activity_sequence"])]
            check(variant["case_count"] == len(rows_list), name + " exact sequence count")
            numeric(variant["percentage"], 100 * len(rows_list) / len(cases), name + " variant share")
            distribution(variant["case_duration_seconds"], [(rows[-1]["_timestamp"] - rows[0]["_timestamp"]).total_seconds() for rows in rows_list], name + " variant duration")
            check(variant["repeated_activity_count"] == len(variant["activity_sequence"]) - len(set(variant["activity_sequence"])), name + " variant repetition")
        assignment_fields = {}
        for section, candidates in (("resources", ["resource_id", "resource_name"]), ("departments", ["department_name", "department_id", "department"])):
            metrics = process[section]
            if metrics is None:
                continue
            member_labels = {member["label"] for member in metrics["members"]}
            field = next((candidate for candidate in candidates if member_labels <= {row.get(candidate) for row in events}), None)
            check(field is not None, name + " identifiable assignment field " + section)
            assignment_fields[section] = field
            changes = sum(left[field] != right[field] for pairs in edge_records.values() for left, right in pairs if left.get(field) and right.get(field))
            check(metrics["changed_assignment_pairs"] == changes, name + " handovers " + section)
            for member in metrics["members"]:
                rows = [row for row in events if row.get(field) == member["label"]]
                check(member["event_count"] == len(rows), name + " assignment event count " + member["label"])
                check(member["case_count"] == len({row["case_id"] for row in rows}), name + " assignment case count " + member["label"])
                values = [row["_processing"] for row in rows if row["_processing"] is not None]
                numeric(member["total_processing_seconds"], sum(values) if values else None, name + " assignment processing " + member["label"])
        source_context[name] = {"cases": cases, "assignment_fields": assignment_fields, "process": process}
        process_summaries.append({"process": name, "cases": len(cases), "events": len(events), "activities": len(activity_records),
                                  "transitions": len(edge_records), "variants": len(variants), "repeated_cases": repeated_cases,
                                  "variants_with_at_least_5_cases": sum(len(value) >= 5 for value in variants.values()),
                                  "cases_on_variants_with_at_least_5_cases": sum(len(value) for value in variants.values() if len(value) >= 5),
                                  "largest_variant_cases": max(map(len, variants.values())), "case_status_counts": dict(statuses),
                                  "mean_case_duration_days": mean(spans) / 86400, "median_case_duration_days": median(spans) / 86400,
                                  "mean_wait_calendar_hours": mean(all_gaps) / 3600 if all_gaps else None,
                                  "median_wait_calendar_hours": median(all_gaps) / 3600 if all_gaps else None,
                                  "measured_interval_pairs": len(all_gaps), "approximate_interval_pairs": len(all_estimates),
                                  "overlapping_interval_pairs": sum(value < 0 for value in all_gaps),
                                  "findings": process["finding_count"], "findings_by_category": process["findings_by_category"]})
    findings = pages("/analytics/findings")
    check(len(findings) == analytics["finding_count"], "Findings total")
    evidence_categories = Counter()
    for item in findings:
        check(item["observed_value"] > item["baseline"]["threshold"], "Finding exceeds actual threshold")
        check(item["cause_status"] == "not_established", "Finding does not claim a cause")
        check(item["potential_impact"]["savings_estimated"] is False, "Finding does not fabricate benefits")
        context = source_context[item["process_type"]]
        check(0 < item["affected_case_count"] <= len(context["cases"]), "Affected case bounds")
        for sample in item["evidence"]["examples"]:
            rows = [records[index - 1] for index in sample["source_rows"]]
            check(all(row["case_id"] == sample["case_id"] and row["process_type"] == item["process_type"] for row in rows), "Evidence belongs to actual source case")
            case = context["cases"][sample["case_id"]]
            category = item["category"]
            if category in {"long_processing", "workload_imbalance"}:
                expected = rows[0]["_processing"]
            elif category == "long_waiting":
                expected = (rows[-1]["_timestamp"] - rows[0]["_timestamp"]).total_seconds() if item["measurement"] == "approximation" else (rows[-1]["_start"] - rows[0]["_end"]).total_seconds()
            elif category in {"delayed_cases", "slow_variant"}:
                expected = (case[-1]["_timestamp"] - case[0]["_timestamp"]).total_seconds()
            elif category == "repeated_activity":
                expected = sum(row["activity"] == item["entity"]["label"] for row in case) - 1
            elif category == "rework_path":
                expected = len(case) - len({row["activity"] for row in case})
            elif category == "frequent_handovers":
                section = "resources" if item["measured_metric"].startswith("resource_") else "departments"
                field = context["assignment_fields"][section]
                expected = sum(left[field] != right[field] for left, right in zip(case, case[1:]) if left.get(field) and right.get(field))
            else:
                raise AssertionError("Unverified finding category: " + category)
            numeric(sample["value"], expected, "Independent evidence value for " + category)
            evidence_categories[category] += 1
    recommendations = pages("/recommendations")
    finding_ids = {item["id"] for item in findings}
    for recommendation in recommendations:
        check(set(recommendation["finding_ids"]) <= finding_ids, "Recommendation cites actual evidence")
        check(recommendation["expected_improvement"] is None, "No fabricated improvement")
    check(hashlib.sha256(source.read_bytes()).hexdigest() == initial_hash, "Source preserved by verification")
    return {"passed": True, "checks_passed": checks, "dataset_id": dataset_id,
            "source_sha256": initial_hash, "source_file": str(source.resolve()),
            "discovery_analysis_id": discovery["analysis_id"], "analytics_analysis_id": analytics["analysis_id"],
            "event_count": len(records), "case_count": len(groups), "process_count": len(process_summaries),
            "case_status_configuration": {"attribute": status_attribute, "values": options.get("case_status_values", {})},
            "processes": process_summaries, "finding_count": len(findings),
            "finding_categories": dict(Counter(item["category"] for item in findings)),
            "independently_checked_evidence_samples": dict(evidence_categories),
            "recommendation_count": len(recommendations),
            "scope": "Read-only comparison of source CSV with actual uploaded analysis; no process-engine imports or synthetic flags used."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--source-folder", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify(args.dataset_id, args.source_folder, args.base_url)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
