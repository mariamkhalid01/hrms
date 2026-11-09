"""Evidence-based event-log validation before canonical events are persisted."""

import json
import math
import re
from collections import defaultdict
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from app.services.mapping.mapper import CANONICAL_FIELDS, REQUIRED_FIELDS
from app.services.normalization.normalizer import normalize_events, parse_timestamps, source_value


def _cell(value: Any) -> str | None:
    value = source_value(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_and_normalize(
    frame: pd.DataFrame,
    mapping: dict,
    timezone: str = "UTC",
    timestamp_format: str | None = None,
    day_first: bool = False,
    on_normalize=None,
) -> tuple[dict, pd.DataFrame | None]:
    source = frame.reset_index(drop=True)
    issues: list[dict] = []
    canonical: dict[str, list[Any]] = {}
    count = len(source)

    def issue(code, severity, message, resolution, field=None, indexes=None, values=None):
        affected = sorted(set(indexes or []))
        issues.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "resolution": resolution,
                "field": field,
                "count": len(affected) if indexes is not None else count,
                "row_numbers": [index + 1 for index in affected[:10]],
                "sample_values": list(dict.fromkeys(str(value) for value in (values or [])))[:10],
            }
        )

    def finish(normalized=None):
        case_values = canonical.get("case_id", [])
        process_values = canonical.get("process_type", [])
        pairs = {
            (process, case)
            for process, case in zip(process_values, case_values, strict=False)
            if process and case
        }
        counts = {
            level: sum(item["severity"] == level for item in issues)
            for level in ("error", "warning", "info")
        }
        return {
            "valid": counts["error"] == 0,
            "summary": {
                "event_count": count,
                "case_count": len(pairs),
                "process_count": len({process for process, _ in pairs}),
                "error_count": counts["error"],
                "warning_count": counts["warning"],
                "info_count": counts["info"],
            },
            "issues": issues,
            "normalized_preview": normalized.head(10).to_dict(orient="records")
            if normalized is not None
            else [],
            "timezone": "UTC",
            "source_timezone": timezone,
        }, normalized

    if count == 0:
        issue(
            "EMPTY_DATASET",
            "error",
            "The event log has no data records.",
            "Upload a CSV containing event records.",
        )
    if not source.columns.is_unique:
        issue(
            "DUPLICATE_SOURCE_COLUMNS",
            "error",
            "Source column names are not unique.",
            "Rename duplicate CSV headers before uploading.",
        )
        return finish()
    unknown = set(mapping) - set(CANONICAL_FIELDS)
    if unknown:
        issue(
            "UNKNOWN_MAPPING_FIELD",
            "error",
            "The mapping contains unsupported canonical fields.",
            "Use the supported mapping fields.",
            values=sorted(unknown),
        )
    for field in CANONICAL_FIELDS:
        column = mapping.get(field)
        if not column:
            canonical[field] = [None] * count
            if field in REQUIRED_FIELDS:
                issue(
                    "REQUIRED_MAPPING_MISSING",
                    "error",
                    f"Map a source column to {field}.",
                    "Select the corresponding CSV column.",
                    field,
                )
        elif not isinstance(column, str) or column not in source.columns:
            canonical[field] = [None] * count
            issue(
                "MAPPING_COLUMN_NOT_FOUND",
                "error",
                f"The mapped source column for {field} does not exist.",
                "Choose a column from this uploaded CSV.",
                field,
                values=[column],
            )
        else:
            canonical[field] = [_cell(value) for value in source[column]]

    reused: dict[str, list[str]] = defaultdict(list)
    for field in CANONICAL_FIELDS:
        column = mapping.get(field)
        if isinstance(column, str) and column in source.columns:
            reused[column].append(field)
    for column, fields in reused.items():
        if len(fields) > 1 and set(fields) != {"timestamp", "activity_end"}:
            issue(
                "MAPPING_COLUMN_REUSED",
                "error",
                f"The source column {column} is assigned to multiple fields.",
                "Map distinct concepts to distinct columns. "
                "Timestamp and activity end may share a column.",
                values=fields,
            )

    if not mapping.get("process_type"):
        canonical["process_type"] = ["Single process"] * count
        issue(
            "SINGLE_PROCESS_ASSUMED",
            "info",
            "No process field is mapped; cases will belong to Single process.",
            "Map a process column if the file contains different workflows.",
            "process_type",
        )
    unmapped = [
        field
        for field in CANONICAL_FIELDS
        if field not in REQUIRED_FIELDS and not mapping.get(field)
    ]
    if unmapped:
        issue(
            "OPTIONAL_FIELDS_UNMAPPED",
            "info",
            "Some optional fields are not mapped.",
            "Map any available optional columns; unmapped source data remains in attributes.",
            values=unmapped,
        )
    for field in CANONICAL_FIELDS:
        if not mapping.get(field):
            continue
        empty = [index for index, value in enumerate(canonical[field]) if value is None]
        if empty:
            required = field in REQUIRED_FIELDS or field == "process_type"
            issue(
                "REQUIRED_VALUE_MISSING" if required else "OPTIONAL_VALUE_MISSING",
                "error" if required else "warning",
                f"{field} is empty in {len(empty)} records.",
                "Correct required cells or revise the mapping."
                if required
                else "Review missing values; they will be preserved as null.",
                field,
                empty,
            )
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        issue(
            "INVALID_TIMEZONE",
            "error",
            "The selected timezone is not a recognized IANA timezone.",
            "Use a name such as UTC, Africa/Cairo, or Europe/Berlin.",
            "timezone",
            values=[timezone],
        )
        return finish()
    if any(
        item["code"]
        in {
            "UNKNOWN_MAPPING_FIELD",
            "MAPPING_COLUMN_NOT_FOUND",
            "MAPPING_COLUMN_REUSED",
            "REQUIRED_MAPPING_MISSING",
        }
        for item in issues
    ):
        return finish()

    parsed_times = {}
    for field in ("timestamp", "activity_start", "activity_end"):
        parsed, failed = parse_timestamps(canonical[field], timezone, timestamp_format, day_first)
        parsed_times[field] = parsed
        for failure, indexes in failed.items():
            if not indexes:
                continue
            messages = {
                "invalid": (
                    "INVALID_TIMESTAMP",
                    "contains invalid or unsupported timestamps",
                    "Correct the source values or select the matching timestamp format.",
                ),
                "ambiguous": (
                    "DST_AMBIGUOUS_TIME",
                    "contains local times repeated during a daylight-saving transition",
                    "Provide explicit UTC offsets for these timestamps.",
                ),
                "nonexistent": (
                    "DST_NONEXISTENT_TIME",
                    "contains local times skipped during a daylight-saving transition",
                    "Correct these local timestamps or provide their actual UTC instants.",
                ),
            }
            code, message, resolution = messages[failure]
            issue(
                code,
                "error",
                f"{field} {message}.",
                resolution,
                field,
                indexes,
                [canonical[field][i] for i in indexes],
            )
        if not timestamp_format:
            ambiguous = []
            for index, value in enumerate(canonical[field]):
                match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-]\d{2,4}(?:\D|$)", value or "")
                if (
                    match
                    and 1 <= int(match[1]) <= 12
                    and 1 <= int(match[2]) <= 12
                    and match[1] != match[2]
                ):
                    ambiguous.append(index)
            if ambiguous:
                interpretation = "day/month/year" if day_first else "month/day/year"
                issue(
                    "AMBIGUOUS_DATE_ORDER",
                    "warning",
                    f"{field} has ambiguous day/month values, "
                    f"currently interpreted as {interpretation}.",
                    "Confirm the day-first choice or provide an explicit timestamp format.",
                    field,
                    ambiguous,
                    [canonical[field][i] for i in ambiguous],
                )

    wrong_interval, outside_interval, end_mismatch = [], [], []
    for index, (stamp, start, end) in enumerate(
        zip(
            parsed_times["timestamp"],
            parsed_times["activity_start"],
            parsed_times["activity_end"],
            strict=True,
        )
    ):
        if start is not None and end is not None and start > end:
            wrong_interval.append(index)
        if stamp is not None and (
            (start is not None and stamp < start) or (end is not None and stamp > end)
        ):
            outside_interval.append(index)
        elif stamp is not None and end is not None and stamp != end:
            end_mismatch.append(index)
    if wrong_interval:
        issue(
            "START_AFTER_END",
            "error",
            "Activity start occurs after activity end.",
            "Correct interval values or their column mapping.",
            "activity_start",
            wrong_interval,
        )
    if outside_interval:
        issue(
            "TIMESTAMP_OUTSIDE_INTERVAL",
            "error",
            "Event timestamp falls outside its activity interval.",
            "Use the event completion timestamp and correct the start/end mapping.",
            "timestamp",
            outside_interval,
        )
    if end_mismatch:
        issue(
            "TIMESTAMP_END_MISMATCH",
            "warning",
            "Event timestamps differ from their activity completion times.",
            "Confirm the timestamp meaning; map the completion time for completion-based mining.",
            "timestamp",
            end_mismatch,
        )

    duplicate_indexes = [int(index) for index in source.index[source.duplicated(keep=False)]]
    if duplicate_indexes:
        issue(
            "DUPLICATE_RECORDS",
            "warning",
            "Exact duplicate source records were found and will be preserved.",
            "Remove duplicates in the source if they are accidental; no rows are silently dropped.",
            indexes=duplicate_indexes,
        )
    orders: list[int | None] = []
    invalid_orders = []
    for index, value in enumerate(canonical["event_order"]):
        try:
            if value is None:
                orders.append(None)
            elif not re.fullmatch(r"\+?\d+(?:\.0+)?", value) or int(value.split(".")[0]) <= 0:
                raise ValueError
            else:
                order = int(value.split(".")[0])
                if order > 2**63 - 1:
                    raise ValueError
                orders.append(order)
        except (ValueError, OverflowError):
            invalid_orders.append(index)
            orders.append(None)
    if invalid_orders:
        issue(
            "INVALID_EVENT_ORDER",
            "error",
            "Mapped event order must contain positive whole numbers.",
            "Correct the order values or leave event order unmapped "
            "to use stable timestamp ordering.",
            "event_order",
            invalid_orders,
        )
    bad_cost = []
    for index, value in enumerate(canonical["cost"]):
        if value is None:
            continue
        try:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError
            canonical["cost"][index] = number
        except ValueError:
            bad_cost.append(index)
            canonical["cost"][index] = None
    if bad_cost:
        issue(
            "NONNUMERIC_COST",
            "warning",
            "Some cost values are not finite numbers; canonical cost will be null.",
            "Correct the values or acknowledge that original text remains in source attributes.",
            "cost",
            bad_cost,
            [source.iloc[i][mapping["cost"]] for i in bad_cost],
        )

    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    case_processes: dict[str, set[str]] = defaultdict(set)
    for index, (process, case) in enumerate(
        zip(canonical["process_type"], canonical["case_id"], strict=True)
    ):
        if process and case:
            groups[(process, case)].append(index)
            case_processes[case].add(process)
    collisions = {case for case, processes in case_processes.items() if len(processes) > 1}
    if collisions:
        indexes = [i for i, case in enumerate(canonical["case_id"]) if case in collisions]
        issue(
            "CASE_ID_SHARED_ACROSS_PROCESSES",
            "warning",
            "Case IDs occur in more than one process; they will be kept as separate cases.",
            "Review process classification. A collision-safe process/case key prevents merging.",
            "case_id",
            indexes,
            sorted(collisions),
        )
    singletons, disordered, repeated_orders, order_gaps, order_conflicts = [], [], [], [], []
    for indexes in groups.values():
        if len(indexes) == 1:
            singletons.extend(indexes)
        instants = [parsed_times["timestamp"][i] for i in indexes]
        if all(value is not None for value in instants) and any(
            a > b for a, b in zip(instants, instants[1:], strict=False)
        ):
            disordered.extend(indexes)
        present = [orders[i] for i in indexes if orders[i] is not None]
        if len(present) != len(set(present)):
            repeated_orders.extend(indexes)
        elif present and sorted(present) != list(range(1, len(present) + 1)):
            order_gaps.extend(indexes)
        time_orders = defaultdict(list)
        for index in indexes:
            instant = parsed_times["timestamp"][index]
            if instant is not None and orders[index] is not None:
                time_orders[instant].append(orders[index])
        previous_max = 0
        for instant in sorted(time_orders):
            if min(time_orders[instant]) < previous_max:
                order_conflicts.extend(indexes)
                break
            previous_max = max(previous_max, max(time_orders[instant]))
    if singletons:
        issue(
            "SINGLE_EVENT_CASES",
            "warning",
            "Some cases contain one event, so their transitions cannot be analyzed.",
            "Confirm the sample is complete or acknowledge these limited cases.",
            "case_id",
            singletons,
        )
    if disordered:
        issue(
            "SOURCE_SEQUENCE_DISORDER",
            "warning",
            "Some case records are not chronological in the uploaded file.",
            "Processing sorts by timestamp, then explicit event order for ties, then source row.",
            "timestamp",
            disordered,
        )
    if repeated_orders:
        issue(
            "DUPLICATE_EVENT_ORDER",
            "warning",
            "Some cases repeat source event-order values.",
            "Review the sequence. Timestamp and source row break ties; "
            "canonical order is regenerated.",
            "event_order",
            repeated_orders,
        )
    if order_gaps:
        issue(
            "EVENT_ORDER_GAPS",
            "warning",
            "Some cases have noncontiguous source event-order values.",
            "Review whether events are missing; canonical event order will be contiguous.",
            "event_order",
            order_gaps,
        )
    if order_conflicts:
        issue(
            "EVENT_ORDER_TIME_CONFLICT",
            "warning",
            "Some source event-order values conflict with chronological timestamp order.",
            "Review timestamp meanings and source sequence. Processing prioritizes timestamps "
            "and preserves the supplied sequence as source_event_order.",
            "event_order",
            order_conflicts,
        )

    # Compare normalized content before sorting so duplicate IDs cannot conceal conflicting records.
    identities: dict[str, list[tuple[int, str]]] = defaultdict(list)
    mapped_columns = {column for column in mapping.values() if isinstance(column, str)}
    for index, (event_id, row) in enumerate(
        zip(canonical["event_id"], source.itertuples(index=False, name=None), strict=True)
    ):
        if event_id is None:
            continue
        content = {field: canonical[field][index] for field in CANONICAL_FIELDS}
        content["event_order"] = orders[index]
        for field, timestamps in parsed_times.items():
            content[field] = (
                timestamps[index].isoformat() if timestamps[index] is not None else None
            )
        content["attributes"] = {
            column: source_value(value)
            for column, value in zip(source.columns, row, strict=True)
            if column not in mapped_columns
        }
        identities[event_id].append(
            (index, json.dumps(content, sort_keys=True, ensure_ascii=False))
        )
    conflicting, repeated = [], []
    for entries in identities.values():
        if len(entries) > 1:
            target = (
                conflicting if len({fingerprint for _, fingerprint in entries}) > 1 else repeated
            )
            target.extend(index for index, _ in entries)
    if conflicting:
        issue(
            "EVENT_ID_CONFLICT",
            "error",
            "The same event ID identifies different event contents.",
            "Correct conflicting identifiers or source records before processing.",
            "event_id",
            conflicting,
            [canonical["event_id"][i] for i in conflicting],
        )
    if repeated:
        issue(
            "DUPLICATE_EVENT_ID",
            "warning",
            "Equivalent normalized events repeat the same event ID and will be preserved.",
            "Confirm repeated records are intended; no automatic deduplication is performed.",
            "event_id",
            repeated,
        )
    if any(item["severity"] == "error" for item in issues):
        return finish()
    if on_normalize:
        on_normalize()
    return finish(normalize_events(source, canonical, parsed_times, orders))
