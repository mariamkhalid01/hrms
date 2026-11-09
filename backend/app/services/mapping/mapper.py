"""Conservative column-name suggestions; users confirm mappings before processing."""

import re

REQUIRED_FIELDS = ("case_id", "activity", "timestamp")
CANONICAL_FIELDS = REQUIRED_FIELDS + (
    "process_type",
    "event_id",
    "resource_id",
    "resource_name",
    "resource_role",
    "department",
    "activity_start",
    "activity_end",
    "cost",
    "outcome",
    "status",
    "event_order",
)

ALIASES = {
    "case_id": (
        "case_id",
        "caseid",
        "case",
        "case:concept:name",
        "case_identifier",
        "process_instance_id",
    ),
    "activity": ("activity", "activity_name", "event_name", "concept:name", "task", "step"),
    "timestamp": (
        "timestamp",
        "time:timestamp",
        "event_timestamp",
        "completion_timestamp",
        "activity_end_timestamp",
        "completed_at",
        "end_time",
    ),
    "process_type": ("process_type", "process_name", "process", "workflow", "workflow_type"),
    "event_id": ("event_id", "eventid", "event_identifier"),
    "resource_id": ("resource_id", "org:resource", "resource", "performer_id", "actor_id"),
    "resource_name": ("resource_name", "performer_name", "actor_name"),
    "resource_role": ("resource_role", "org:role", "role"),
    "department": ("department", "department_id", "department_name", "org:group", "team"),
    "activity_start": (
        "activity_start",
        "activity_start_timestamp",
        "start_timestamp",
        "start_time",
        "started_at",
    ),
    "activity_end": (
        "activity_end",
        "activity_end_timestamp",
        "end_timestamp",
        "completion_timestamp",
        "completed_at",
        "end_time",
    ),
    "cost": ("cost", "activity_cost", "event_cost", "cost:total"),
    "outcome": ("outcome", "result"),
    "status": ("status", "activity_status", "event_status"),
    "event_order": ("event_order", "sequence", "sequence_number", "event_sequence", "order"),
}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    suggestions: dict[str, str | None] = dict.fromkeys(CANONICAL_FIELDS)
    normalized: dict[str, list[str]] = {}
    for column in columns:
        normalized.setdefault(_key(column), []).append(column)
    used: dict[str, str] = {}
    for field in CANONICAL_FIELDS:
        for alias in ALIASES[field]:
            candidates = normalized.get(_key(alias), [])
            if len(candidates) != 1:
                continue
            source = candidates[0]
            shared_completion = field == "activity_end" and used.get(source) == "timestamp"
            if source in used and not shared_completion:
                continue
            suggestions[field] = source
            used.setdefault(source, field)
            break
    return suggestions
