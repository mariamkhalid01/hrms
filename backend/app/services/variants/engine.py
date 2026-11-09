"""Exact variants from PM4Py traces; duration is the observed first-to-last event span."""

import pm4py

from app.services.discovery.log import Case, distribution, stable_id, state_counts


def discover_variants(log, cases: list[Case], process: str) -> list[dict]:
    case_lookup = {case.key: case for case in cases}
    variants = []
    for sequence, traces in pm4py.get_variants_as_tuples(log).items():
        members = [case_lookup[trace.attributes["concept:name"]] for trace in traces]
        observed = distribution([case.duration for case in members])
        variants.append(
            {
                "id": stable_id("variant", process, sequence),
                "activity_sequence": list(sequence),
                "activity_ids": [stable_id("activity", process, label) for label in sequence],
                "case_count": len(members),
                "percentage": 100 * len(members) / len(cases),
                "average_case_duration_seconds": observed["mean"],
                "median_case_duration_seconds": observed["median"],
                "observed_duration_seconds": observed,
                "completed_duration_seconds": distribution(
                    [case.duration for case in members if case.state == "completed"]
                ),
                "case_status_counts": state_counts(members),
            }
        )
    return sorted(variants, key=lambda variant: (-variant["case_count"], variant["id"]))
