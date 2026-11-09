"""Aggregate actual normalized traces using IDs and variants from the mined model."""

from collections import Counter, defaultdict

from app.schemas.analytics import AnalyticsRequest, ProcessPerformance, Thresholds
from app.schemas.discovery import DiscoveryRequest
from app.services.analytics.measurements import (
    known,
    observe,
    processing,
    summarize,
    waiting_summary,
)
from app.services.analytics.resources import assignment_analysis
from app.services.discovery.log import build_log, prepare_frame, stable_id
from app.services.ingestion.errors import DatasetError
from app.services.process_separation.separator import split_processes

SEMANTICS = {
    "case_duration": "Last minus first observed event timestamp; UTC seconds, not business time.",
    "processing": "Activity end minus activity start, only where both mapped timestamps exist.",
    "measured_wait": "Nonnegative gap from previous activity end to next activity start. "
    "an observed gap, not proven idle/queue time or its cause.",
    "approximate_wait": "Consecutive event timestamp difference when the interval pair is missing. "
    "This approximation can include processing and other unobserved work.",
    "overlaps": "Negative gaps are retained separately and excluded from waiting statistics.",
    "completion": "Overall completion rate is null if any case status is unknown. The known-status "
    "rate uses only identified cases and is reported with coverage.",
    "resource_work": "Sums of observed intervals are not utilization, capacity or productivity; "
    "overlapping assignments may be counted more than once.",
    "rework": "Repeated labels show repeated work, not proof of unnecessary repetition.",
    "findings": "Findings support review, not causal conclusions. Excess time is observed "
    "exposure above a threshold, not predicted savings; findings can overlap.",
}


def effective_thresholds(request: AnalyticsRequest, name: str) -> Thresholds:
    base = request.thresholds.model_dump()
    if name in request.process_overrides:
        base.update(request.process_overrides[name].model_dump(exclude_unset=True))
    return Thresholds.model_validate(base)


def validate_overrides(request: AnalyticsRequest, models: list[dict]) -> None:
    names = {model["name"] for model in models}
    if set(request.process_overrides) - names:
        raise DatasetError(
            422, "UNKNOWN_THRESHOLD_PROCESS", "A threshold names an unknown process."
        )
    scopes = [(request.thresholds, models)] + [
        (threshold, [model for model in models if model["name"] == name])
        for name, threshold in request.process_overrides.items()
    ]
    for threshold, scope in scopes:
        activities = {item["label"] for model in scope for item in model["activities"]}
        edges = {item["id"] for model in scope for item in model["transitions"]}
        if (
            set(threshold.processing_seconds_by_activity) - activities
            or set(threshold.waiting_seconds_by_transition) - edges
        ):
            raise DatasetError(
                422,
                "UNKNOWN_THRESHOLD_TARGET",
                "An activity label or transition ID in the thresholds does not exist.",
            )


def process_metrics(frame, model, variants, discovery_options, thresholds):
    _, cases = build_log(frame, discovery_options)
    process = model["name"]
    activity_samples, edge_gaps, edge_estimates = (
        defaultdict(list),
        defaultdict(list),
        defaultdict(list),
    )
    repeats, activity_records, edge_records = (
        defaultdict(list),
        defaultdict(list),
        defaultdict(list),
    )
    durations, full_intervals, statuses = [], [], defaultdict(list)
    variant_cases = defaultdict(list)
    resource_field = next(
        (
            field
            for field in ("resource_id", "resource_name")
            if field in frame and any(known(value) for value in frame[field])
        ),
        None,
    )
    department_field = (
        "department" if "department" in frame and any(known(v) for v in frame.department) else None
    )
    repeat_case_count = 0
    for case in cases:
        sample = observe(case.duration, case.records[0], case.records[-1])
        durations.append(sample)
        statuses[case.state].append(sample)
        sequence = tuple(record["activity"] for record in case.records)
        case_activities = defaultdict(list)
        for record in case.records:
            case_activities[record["activity"]].append(record)
        variant_cases[stable_id("variant", process, sequence)].append((case, sample))
        counts = Counter(sequence)
        repeat_case_count += any(count > 1 for count in counts.values())
        if all(processing(record) is not None for record in case.records):
            span = (
                max(record["activity_end"] for record in case.records)
                - min(record["activity_start"] for record in case.records)
            ).total_seconds()
            full_intervals.append(observe(span, case.records[0], case.records[-1]))
        for label, count in counts.items():
            if count > 1:
                selected = case_activities[label]
                repeats[label].append(observe(count - 1, *selected[:10]))
        for record in case.records:
            activity_records[record["activity"]].append(record)
            if (duration := processing(record)) is not None:
                activity_samples[record["activity"]].append(observe(duration, record))
        for left, right in zip(case.records, case.records[1:], strict=False):
            identifier = stable_id("edge", process, left["activity"], right["activity"])
            edge_records[identifier].append((left, right))
            if known(left.get("activity_end")) and known(right.get("activity_start")):
                gap = (right["activity_start"] - left["activity_end"]).total_seconds()
                edge_gaps[identifier].append(observe(gap, left, right))
            else:
                gap = (right["timestamp"] - left["timestamp"]).total_seconds()
                edge_estimates[identifier].append(observe(gap, left, right))
    labels = {item["id"]: item["label"] for item in model["activities"]}
    incoming_gaps, incoming_estimates = defaultdict(list), defaultdict(list)
    transition_metrics = []
    for edge in model["transitions"]:
        identifier = edge["id"]
        incoming_gaps[edge["target"]].extend(edge_gaps[identifier])
        incoming_estimates[edge["target"]].extend(edge_estimates[identifier])
        handovers = {}
        for category, field in (("resource", resource_field), ("department", department_field)):
            pairs = [
                (left, right)
                for left, right in edge_records[identifier]
                if field and known(left.get(field)) and known(right.get(field))
            ]
            handovers[f"{category}_comparable_pairs"] = len(pairs) if field else None
            handovers[f"{category}_handovers"] = (
                sum(left[field] != right[field] for left, right in pairs) if pairs else None
            )
        transition_metrics.append(
            {
                "id": identifier,
                "source": edge["source"],
                "target": edge["target"],
                "source_label": labels[edge["source"]],
                "target_label": labels[edge["target"]],
                "frequency": edge["frequency"],
                "case_frequency": edge["case_frequency"],
                "waiting": waiting_summary(edge_gaps[identifier], edge_estimates[identifier]),
                **handovers,
            }
        )
    activities = [
        {
            "id": item["id"],
            "label": item["label"],
            "frequency": item["frequency"],
            "case_frequency": item["case_frequency"],
            "repeated_case_count": item["repeated_case_count"],
            "repeated_case_percentage": 100 * item["repeated_case_count"] / item["case_frequency"],
            "extra_occurrences": sum(sample.value for sample in repeats[item["label"]]),
            "processing_seconds": summarize(activity_samples[item["label"]]),
            "processing_coverage_percentage": 100
            * len(activity_samples[item["label"]])
            / item["frequency"],
            "incoming_wait": waiting_summary(
                incoming_gaps[item["id"]], incoming_estimates[item["id"]]
            ),
        }
        for item in model["activities"]
    ]
    counts = model["metadata"]["case_status_counts"]
    known_cases = len(cases) - counts["unknown"]
    resources, resource_context = (
        assignment_analysis(cases, process, resource_field) if resource_field else (None, {})
    )
    departments, department_context = assignment_analysis(cases, process, "department")
    all_processing = [sample for samples in activity_samples.values() for sample in samples]
    all_gaps = [sample for samples in edge_gaps.values() for sample in samples]
    all_estimates = [sample for samples in edge_estimates.values() for sample in samples]
    variant_metrics = []
    for variant in variants:
        sequence = variant["activity_sequence"]
        extra = len(sequence) - len(set(sequence))
        variant_metrics.append(
            {
                "id": variant["id"],
                "activity_sequence": sequence,
                "case_count": variant["case_count"],
                "percentage": variant["percentage"],
                "case_duration_seconds": variant["observed_duration_seconds"],
                "repeated_activity_count": extra,
                "extra_event_percentage": 100 * extra / len(sequence),
                "case_status_counts": variant["case_status_counts"],
            }
        )
    warnings = [
        "Repeated activities and handovers may be legitimate parts of the workflow.",
        "Activity and resource duration comparisons do not control for case complexity.",
    ]
    if all_estimates:
        warnings.append(
            "Missing interval pairs require explicitly labeled waiting-time approximations."
        )
    if counts["unknown"]:
        warnings.append("Unknown case statuses prevent an overall completion-rate estimate.")
    if len(all_processing) < len(frame):
        warnings.append(
            "Processing-time coverage is partial or unavailable; missing durations are not zero."
        )
    if any(sample.value < 0 for sample in all_gaps):
        warnings.append(
            "Overlapping activity intervals are excluded from nonnegative waiting statistics."
        )
    metric = ProcessPerformance.model_validate(
        {
            "id": model["id"],
            "name": process,
            "total_cases": len(cases),
            "total_events": len(frame),
            "case_duration_seconds": summarize(durations),
            "completed_case_duration_seconds": summarize(statuses["completed"]),
            "full_interval_case_duration_seconds": summarize(full_intervals),
            "completion": {
                "status_counts": counts,
                "known_status_cases": known_cases,
                "status_coverage_percentage": 100 * known_cases / len(cases),
                "completion_rate_percentage": 100 * counts["completed"] / len(cases)
                if known_cases == len(cases)
                else None,
                "known_status_completion_rate_percentage": 100 * counts["completed"] / known_cases
                if known_cases
                else None,
            },
            "processing_seconds": summarize(all_processing),
            "waiting": waiting_summary(all_gaps, all_estimates),
            "variant_count": len(variants),
            "repeated_case_count": repeat_case_count,
            "repeated_case_percentage": 100 * repeat_case_count / len(cases),
            "activities": activities,
            "transitions": transition_metrics,
            "resources": resources,
            "departments": departments,
            "effective_thresholds": thresholds,
            "warnings": warnings,
        }
    ).model_dump()
    context = {
        "activity_samples": activity_samples,
        "activity_records": activity_records,
        "repeats": repeats,
        "edge_gaps": edge_gaps,
        "edge_estimates": edge_estimates,
        "durations": durations,
        "statuses": statuses,
        "variant_cases": variant_cases,
        "resources": resource_context,
        "departments": department_context,
    }
    return metric, variant_metrics, context


def analyze(frame, discovery: dict, request: AnalyticsRequest, progress=None):
    from app.services.bottlenecks.engine import detect

    validate_overrides(request, discovery["processes"])
    options = DiscoveryRequest.model_validate(discovery["configuration"])
    prepared = prepare_frame(frame, options)
    models = {model["name"]: model for model in discovery["processes"]}
    results, variants, findings, contexts = [], {}, [], {}
    if progress:
        progress("calculating_performance_metrics")
    for name, partition in split_processes(prepared):
        model = models[name]
        thresholds = effective_thresholds(request, name)
        metric, paths, context = process_metrics(
            partition, model, discovery["variants"][model["id"]], options, thresholds
        )
        results.append(metric)
        variants[model["id"]] = paths
        contexts[model["id"]] = (context, thresholds)
    if progress:
        progress("detecting_bottlenecks")
    for metric in results:
        context, thresholds = contexts[metric["id"]]
        detected = detect(metric, variants[metric["id"]], context, thresholds)
        metric["finding_count"] = len(detected)
        metric["findings_by_category"] = dict(Counter(item["category"] for item in detected))
        findings.extend(detected)
    rank = {"high": 0, "medium": 1, "low": 2}
    findings.sort(
        key=lambda item: (rank[item["severity"]], -item["affected_case_count"], item["id"])
    )
    return results, variants, findings
