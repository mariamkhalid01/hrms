"""Assignment counts and measured work, without inferring capacity or productivity."""

from collections import Counter, defaultdict

from app.services.analytics.measurements import known, observe, processing, summarize
from app.services.discovery.log import stable_id


def assignment_analysis(cases, process: str, field: str) -> tuple[dict | None, dict]:
    members, pairs = defaultdict(list), defaultdict(list)
    per_case, comparable, changed, total = [], 0, 0, 0
    for case in cases:
        total += len(case.records)
        fully_known = all(known(record.get(field)) for record in case.records)
        changes = 0
        for record in case.records:
            if known(record.get(field)):
                members[str(record[field])].append(record)
        for left, right in zip(case.records, case.records[1:], strict=False):
            if known(left.get(field)) and known(right.get(field)):
                comparable += 1
                if left[field] != right[field]:
                    changed += 1
                    changes += 1
                    pairs[(str(left[field]), str(right[field]))].append(observe(1, left, right))
        if fully_known:
            per_case.append(observe(changes, case.records[0], case.records[-1]))
    if not members:
        return None, {}
    known_count = sum(len(records) for records in members.values())
    metrics, contexts, ids = [], {}, {}
    for value, records in sorted(members.items()):
        identifier = stable_id("assignment", process, field, value)
        ids[value] = identifier
        samples = [
            observe(duration, record)
            for record in records
            if (duration := processing(record)) is not None
        ]
        counts = Counter(record["case_id"] for record in records)
        repeats = Counter((record["case_id"], record["activity"]) for record in records)
        roles = (
            sorted(
                {
                    str(record["resource_role"])
                    for record in records
                    if known(record.get("resource_role"))
                }
            )
            if field != "department"
            else []
        )
        names = (
            sorted(
                {
                    str(record["resource_name"])
                    for record in records
                    if known(record.get("resource_name"))
                }
            )
            if field != "department"
            else []
        )
        metrics.append(
            {
                "id": identifier,
                "label": value,
                "names": names[:10],
                "roles": roles,
                "event_count": len(records),
                "case_count": len(counts),
                "activity_count": len({record["activity"] for record in records}),
                "event_share_percentage": 100 * len(records) / known_count,
                "total_processing_seconds": sum(item.value for item in samples)
                if samples
                else None,
                "processing_seconds": summarize(samples),
                "processing_coverage_percentage": 100 * len(samples) / len(records),
                "repeated_case_assignments": sum(count - 1 for count in counts.values()),
                "same_activity_repeat_assignments": sum(count - 1 for count in repeats.values()),
            }
        )
        contexts[identifier] = {"records": records, "processing": samples, "roles": roles}
    return {
        "field": field,
        "known_event_count": known_count,
        "missing_event_count": total - known_count,
        "coverage_percentage": 100 * known_count / total,
        "comparable_adjacent_pairs": comparable,
        "changed_assignment_pairs": changed,
        "same_assignment_pairs": comparable - changed,
        "handover_rate_percentage": 100 * changed / comparable if comparable else None,
        "handovers_per_fully_observed_case": summarize(per_case),
        "fully_observed_case_count": len(per_case),
        "members": metrics,
        "handovers": [
            {
                "source": ids[left],
                "target": ids[right],
                "count": len(samples),
                "affected_case_count": len({item.case_id for item in samples}),
            }
            for (left, right), samples in sorted(pairs.items())
        ],
    }, {"members": contexts, "case_handovers": per_case}
