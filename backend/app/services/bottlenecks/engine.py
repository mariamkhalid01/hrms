"""Explainable screening rules over actual timings, sequences and assignment evidence."""

from collections import defaultdict
from statistics import mean, median

import pandas as pd

from app.schemas.analytics import Finding, Thresholds
from app.services.analytics.measurements import observe
from app.services.discovery.log import stable_id


def baseline(values: list[float], options: Thresholds, cohort: str, business=None):
    if business is not None:
        return {
            "method": "business_threshold",
            "cohort": cohort,
            "sample_count": len(values),
            "comparison_value": float(median(values)) if values else None,
            "threshold": business,
        }
    if len(values) < options.minimum_samples:
        return None
    q1, q3 = pd.Series(values, dtype=float).quantile([0.25, 0.75], interpolation="linear")
    center = float(median(values))
    return {
        "method": "robust_upper_fence",
        "cohort": cohort,
        "sample_count": len(values),
        "comparison_value": center,
        "q1": float(q1),
        "q3": float(q3),
        "threshold": max(
            float(q3 + options.iqr_multiplier * (q3 - q1)),
            center * options.minimum_relative_increase,
        ),
    }


def configured(limit: float, count: int, cohort: str):
    return {
        "method": "configured_screening_rule",
        "cohort": cohort,
        "sample_count": count,
        "comparison_value": limit,
        "threshold": limit,
    }


def entity(kind, identifier, label, **fields):
    return {"kind": kind, "id": identifier, "label": label, **fields}


def finding(
    process,
    target,
    category,
    metric,
    unit,
    measurement,
    observed,
    reference,
    affected,
    eligible,
    explanation,
    impact,
    caveats=None,
    excess=None,
):
    ratio = observed / reference["threshold"] if reference["threshold"] > 0 else 1.5
    severity = "high" if ratio >= 2 else ("medium" if ratio >= 1.25 else "low")
    if measurement == "approximation" and severity == "high":
        severity = "medium"
    examples = sorted(affected, key=lambda item: (-item.value, item.case_id, item.rows))[:10]
    return Finding.model_validate(
        {
            "id": stable_id(
                "finding", process["id"], category, target["id"], metric, reference["cohort"]
            ),
            "process_id": process["id"],
            "process_type": process["name"],
            "entity": target,
            "category": category,
            "measured_metric": metric,
            "unit": unit,
            "measurement": measurement,
            "observed_value": observed,
            "baseline": reference,
            "affected_case_count": len({item.case_id for item in affected}),
            "severity": severity,
            "evidence": {
                "explanation": explanation,
                "eligible_observation_count": len(eligible),
                "affected_observation_count": len(affected),
                "eligible_case_count": len({item.case_id for item in eligible}),
                "examples": [
                    {
                        "case_id": item.case_id,
                        "source_rows": list(item.rows[:10]),
                        "value": item.value,
                        "unit": "count" if unit == "percentage" else unit,
                    }
                    for item in examples
                ],
                "caveats": caveats or [],
            },
            "potential_impact": {"description": impact, "observed_excess_seconds": excess},
        }
    ).model_dump()


def duration_findings(process, groups, options, category, metric, measurement):
    """Within-entity outliers, or a persistently long entity relative to process peers."""
    results = []
    peer_means = [
        mean(sample.value for sample in samples)
        for _, samples, _ in groups
        if len(samples) >= options.minimum_samples
    ]
    peers = baseline(peer_means, options, f"{metric}: entity means within this process")
    for target, samples, business in groups:
        if not samples:
            continue
        values = [sample.value for sample in samples]
        reference = baseline(values, options, f"{metric}: same {target['kind']}", business)
        if reference is None:
            continue
        affected = [sample for sample in samples if sample.value > reference["threshold"]]
        mode = "individual observations exceed"
        observed = mean(sample.value for sample in affected) if affected else 0
        if len({sample.case_id for sample in affected}) < options.minimum_affected_cases:
            if (
                business is not None
                or peers is None
                or len(samples) < options.minimum_samples
                or mean(values) <= peers["threshold"]
            ):
                continue
            reference, affected, observed = peers, samples, mean(values)
            mode = "the entity mean exceeds"
        if len({sample.case_id for sample in affected}) < options.minimum_affected_cases:
            continue
        caveats = [
            "Longer durations can be legitimate; task complexity and causes are not established."
        ]
        if measurement == "approximation":
            caveats.append(
                "Consecutive-event gaps may include processing; this is not measured waiting."
            )
        elif category == "long_waiting":
            caveats.append(
                "Nonnegative interval gaps do not prove that resources or cases were idle."
            )
        results.append(
            finding(
                process,
                target,
                category,
                metric,
                "seconds",
                measurement,
                observed,
                reference,
                affected,
                samples,
                f"{target['label']}: {mode} the reported {reference['method']} threshold. "
                "Observed value is the mean of affected observations "
                "(or the entire peer-outlier entity).",
                "This time exposure identifies a location to review for process delay; "
                "no savings are estimated.",
                caveats,
                sum(max(0, sample.value - reference["threshold"]) for sample in affected),
            )
        )
    return results


def repeat_findings(process, variants, context, options):
    results = []
    for item in process["activities"]:
        affected = context["repeats"][item["label"]]
        if (
            len(affected) < options.minimum_affected_cases
            or item["repeated_case_percentage"] <= options.repeated_case_percentage
        ):
            continue
        eligible = [observe(1, record) for record in context["activity_records"][item["label"]]]
        results.append(
            finding(
                process,
                entity("activity", item["id"], item["label"]),
                "repeated_activity",
                "cases_repeating_activity_percentage",
                "percentage",
                "measured",
                item["repeated_case_percentage"],
                configured(
                    options.repeated_case_percentage,
                    item["case_frequency"],
                    "Cases containing this activity",
                ),
                affected,
                eligible,
                "The share of involved cases repeating this activity exceeds the screening rate. "
                "Evidence example values are extra occurrences within each case.",
                "Repeated work may add effort; necessity and avoidable cost are not established.",
                [
                    "Repeats can be expected iterations or acknowledged duplicates, "
                    "not necessarily rework."
                ],
            )
        )
    for variant in variants:
        if (
            variant["case_count"] < options.minimum_affected_cases
            or variant["extra_event_percentage"] <= options.variant_repetition_percentage
        ):
            continue
        samples = [
            observe(variant["repeated_activity_count"], case.records[0], case.records[-1])
            for case, _ in context["variant_cases"][variant["id"]]
        ]
        results.append(
            finding(
                process,
                entity("variant", variant["id"], " → ".join(variant["activity_sequence"])),
                "rework_path",
                "extra_event_percentage",
                "percentage",
                "measured",
                variant["extra_event_percentage"],
                configured(
                    options.variant_repetition_percentage,
                    variant["case_count"],
                    "Repeated-label events divided by events in this variant",
                ),
                samples,
                samples,
                "This observed variant has a repeated-event share above the configured screening "
                "threshold. Example values are extra events per case.",
                "This path warrants review for repeated work; no avoidability is assumed.",
                ["A repeated path is a rework candidate, not proof of unnecessary steps."],
            )
        )
    return results


def case_findings(process, variants, context, options):
    results = []
    for state, samples in sorted(context["statuses"].items()):
        reference = baseline(
            [item.value for item in samples],
            options,
            f"Observed case spans in this process with status {state}",
            options.case_duration_seconds,
        )
        if reference is None:
            continue
        affected = [item for item in samples if item.value > reference["threshold"]]
        caveats = [
            "Duration covers the first through last observed event, not work outside the log.",
            f"This comparison uses only the {state} case-status cohort.",
        ]
        if len(affected) >= options.minimum_affected_cases:
            results.append(
                finding(
                    process,
                    entity("process", process["id"], process["name"]),
                    "delayed_cases",
                    f"observed_case_duration_seconds:{state}",
                    "seconds",
                    "observed_span",
                    mean(item.value for item in affected),
                    reference,
                    affected,
                    samples,
                    "Case spans exceed the reported threshold within the same status cohort; "
                    "the observed value is their mean.",
                    "These cases carry unusually long observed time "
                    "spans and merit review; missed SLAs require a business threshold.",
                    caveats,
                    sum(item.value - reference["threshold"] for item in affected),
                )
            )
        for variant in variants:
            cohort = [
                sample
                for case, sample in context["variant_cases"][variant["id"]]
                if case.state == state
            ]
            if len(cohort) < options.minimum_affected_cases:
                continue
            observed = mean(item.value for item in cohort)
            if observed > reference["threshold"]:
                results.append(
                    finding(
                        process,
                        entity("variant", variant["id"], " → ".join(variant["activity_sequence"])),
                        "slow_variant",
                        f"mean_observed_case_duration_seconds:{state}",
                        "seconds",
                        "observed_span",
                        observed,
                        reference,
                        cohort,
                        samples,
                        "The variant mean exceeds the same-process, same-status case threshold; "
                        "all cases in this variant/status cohort are counted as exposed.",
                        "This path is associated with longer spans; causality is not established.",
                        caveats,
                        sum(max(0, item.value - reference["threshold"]) for item in cohort),
                    )
                )
    return results


def assignment_findings(process, context, options):
    results = []
    for section, kind in (("resources", "resource"), ("departments", "department")):
        metrics = process[section]
        if metrics is None:
            continue
        samples = context[section]["case_handovers"]
        reference = baseline(
            [item.value for item in samples],
            options,
            f"{kind} handovers per fully observed case within this process",
            options.handovers_per_case,
        )
        if reference is not None:
            affected = [item for item in samples if item.value > reference["threshold"]]
            if len(affected) >= options.minimum_affected_cases:
                results.append(
                    finding(
                        process,
                        entity("process", process["id"], process["name"]),
                        "frequent_handovers",
                        f"{kind}_handovers_per_case",
                        "count",
                        "measured",
                        mean(item.value for item in affected),
                        reference,
                        affected,
                        samples,
                        "Cases with observed assignments exceed the handover-count threshold. "
                        "Missing assignments are not bridged or counted as handovers.",
                        "Assignment changes warrant coordination review; necessity and delay "
                        "causation have not been established.",
                        ["Case complexity can require more handovers."],
                    )
                )
        # Compare measured effort, not frequency alone. Require full timing coverage.
        cohorts = defaultdict(list)
        for member in metrics["members"]:
            if member["processing_coverage_percentage"] != 100:
                continue
            roles = member["roles"]
            if kind == "resource" and len(roles) > 1:
                continue
            cohort = roles[0] if roles else "role unspecified"
            cohorts[cohort].append(member)
        for role, members in cohorts.items():
            reference = baseline(
                [item["total_processing_seconds"] for item in members],
                options,
                f"{kind} total measured work in this process; {role}",
            )
            if reference is None:
                continue
            for member in members:
                observed = member["total_processing_seconds"]
                samples = context[section]["members"][member["id"]]["processing"]
                if (
                    observed <= reference["threshold"]
                    or member["case_count"] < options.minimum_affected_cases
                ):
                    continue
                results.append(
                    finding(
                        process,
                        entity(kind, member["id"], member["label"]),
                        "workload_imbalance",
                        "total_observed_processing_seconds",
                        "seconds",
                        "measured",
                        observed,
                        reference,
                        samples,
                        samples,
                        "Total observed processing time exceeds the robust "
                        "peer threshold. Require full interval coverage; resources "
                        "with an identified single role are compared within that role.",
                        "Work is concentrated on this assignment; review capacity and task mix "
                        "before concluding overload.",
                        [
                            "This is not utilization or a productivity ranking.",
                            "Capacity, availability, complexity and task mix are not controlled.",
                            "Partial timing coverage and multiple-role resources are excluded.",
                        ],
                    )
                )
    return results


def detect(process, variants, context, options):
    processing_groups = [
        (
            entity("activity", item["id"], item["label"]),
            context["activity_samples"][item["label"]],
            options.processing_seconds_by_activity.get(item["label"], options.processing_seconds),
        )
        for item in process["activities"]
    ]
    results = duration_findings(
        process, processing_groups, options, "long_processing", "processing_seconds", "measured"
    )
    for approximation in (False, True):
        groups = []
        for edge in process["transitions"]:
            samples = (
                context["edge_estimates"][edge["id"]]
                if approximation
                else [item for item in context["edge_gaps"][edge["id"]] if item.value >= 0]
            )
            groups.append(
                (
                    entity(
                        "transition",
                        edge["id"],
                        f"{edge['source_label']} → {edge['target_label']}",
                        source=edge["source"],
                        target=edge["target"],
                    ),
                    samples,
                    options.waiting_seconds_by_transition.get(edge["id"], options.waiting_seconds),
                )
            )
        results.extend(
            duration_findings(
                process,
                groups,
                options,
                "long_waiting",
                "approximate_wait_seconds" if approximation else "measured_wait_seconds",
                "approximation" if approximation else "measured",
            )
        )
    results.extend(repeat_findings(process, variants, context, options))
    results.extend(case_findings(process, variants, context, options))
    results.extend(assignment_findings(process, context, options))
    return results
