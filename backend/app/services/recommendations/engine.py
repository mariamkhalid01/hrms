"""Review actions selected by actual evidence; no invented causes or projected benefits."""

from app.schemas.workspace import Recommendation
from app.services.discovery.log import stable_id

RULES = {
    "long_processing": (
        "Review long processing intervals",
        [
            "Inspect cited intervals and compare case complexity with typical examples.",
            "Check with the owner whether requirements or repeated checks explain longer work.",
            "Pilot a change only after confirming an avoidable step; compare like-for-like cases.",
        ],
        "Track median processing duration and coverage for this activity.",
    ),
    "long_waiting": (
        "Investigate long transition gaps",
        [
            "Review the cited transitions, working schedules and timestamp coverage.",
            "Establish whether the observed gap includes required waiting or unrecorded work.",
            "If avoidable waiting is confirmed, trial a documented routing or ownership change.",
        ],
        "Track measured gaps separately from timestamp-based approximations.",
    ),
    "repeated_activity": (
        "Review repeated activity execution",
        [
            "Inspect repeats and check whether they are intended iterations or duplicates.",
            "Identify actual repeated requests or corrections before proposing a change.",
            "Test a guidance change only for confirmed unnecessary repetition.",
        ],
        "Track the share of involved cases repeating this activity.",
    ),
    "rework_path": (
        "Review a repetition-heavy path",
        [
            "Compare this path's cases with their attributes and intended process rules.",
            "Confirm which repetitions are required and which can be prevented.",
            "Pilot a narrowly scoped prevention change and check whether the variant mix changes.",
        ],
        "Track this variant's share, repeated events and observed duration.",
    ),
    "delayed_cases": (
        "Investigate long observed case spans",
        [
            "Review the cited cases, their status and missing events before calling them overdue.",
            "Validate time targets with the process owner and account for working schedules.",
            "Review verified overdue cases with their owners and record the actual causes.",
        ],
        "Track duration within the same case-status cohort and agreed service target.",
    ),
    "slow_variant": (
        "Examine a longer-duration variant",
        [
            "Compare this path with typical paths for cases of similar complexity and status.",
            "Locate the transitions contributing to the observed span using the case timeline.",
            "Test a change only after verifying that the path contains avoidable work or waiting.",
        ],
        "Track variant case count, mean/median duration and case-status mix.",
    ),
    "frequent_handovers": (
        "Review frequent assignment changes",
        [
            "Inspect the cited cases and verify whether assignment changes were required.",
            "Clarify ownership at transitions where coordination problems are confirmed.",
            "Trial reduced handovers only where responsibilities and controls allow it.",
        ],
        "Track handovers per fully observed case and measured transition gaps.",
    ),
    "workload_imbalance": (
        "Review observed workload concentration",
        [
            "Compare measured work with actual capacity, availability, role and case complexity.",
            "Check whether concentration reflects specialization, overlaps or a real constraint.",
            "Consider assignment changes only after reviewing skills and available capacity.",
        ],
        "Track observed processing totals, interval coverage and actual capacity separately.",
    ),
}


def recommend(findings: list[dict]) -> list[dict]:
    results = []
    for item in findings:
        title, actions, measure = RULES[item["category"]]
        reference = item["baseline"]
        results.append(
            Recommendation(
                id=stable_id("recommendation", item["id"]),
                process_id=item["process_id"],
                process_type=item["process_type"],
                title=title,
                category=item["category"],
                priority=item["severity"],
                entity=item["entity"],
                finding_ids=[item["id"]],
                evidence_summary=(
                    f"{item['entity']['label']}: {item['measured_metric']} was "
                    f"{item['observed_value']:.3g} {item['unit']}, above the reported "
                    f"{reference['threshold']:.3g} threshold; "
                    f"{item['affected_case_count']} cases were affected or exposed."
                ),
                actions=actions,
                measurement_plan=[measure, "Compare an agreed pilot with a comparable baseline."],
                caveats=[
                    *item["evidence"]["caveats"],
                    "Causes are unconfirmed. Improvement is not estimated.",
                ],
                affected_case_count=item["affected_case_count"],
            ).model_dump()
        )
    return results
