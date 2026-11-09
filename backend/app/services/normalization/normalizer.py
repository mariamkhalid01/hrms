"""Canonical event construction, strict timestamp parsing, and stable ordering."""

import json
import warnings
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


def source_value(value: Any) -> Any:
    """Preserve source values while keeping attributes safe for JSON serialization."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def parse_timestamps(
    values: list[str | None],
    timezone: str,
    timestamp_format: str | None,
    day_first: bool,
) -> tuple[list[pd.Timestamp | None], dict[str, list[int]]]:
    """Return UTC instants plus failure indexes; never infer through a DST ambiguity."""
    parsed: list[pd.Timestamp | None] = []
    failures: dict[str, list[int]] = {"invalid": [], "ambiguous": [], "nonexistent": []}
    cache: dict[str, tuple[pd.Timestamp | None, str | None]] = {}
    zone = ZoneInfo(timezone)
    for index, value in enumerate(values):
        if value is None:
            parsed.append(None)
            continue
        if value not in cache:
            try:
                with warnings.catch_warnings():
                    # Unrecognized timezone abbreviations must not be silently discarded.
                    warnings.simplefilter("error")
                    timestamp = pd.to_datetime(
                        value,
                        format=timestamp_format or "mixed",
                        dayfirst=day_first,
                        errors="raise",
                    )
                if pd.isna(timestamp):
                    raise ValueError("Missing timestamp")
                if timestamp.tzinfo is None:
                    timestamp = timestamp.tz_localize(zone, ambiguous="raise", nonexistent="raise")
                timestamp = timestamp.tz_convert("UTC")
                # Canonical sorting uses nanosecond pandas timestamps; reject out-of-range values.
                timestamp = timestamp.as_unit("ns")
                cache[value] = (timestamp, None)
            except Exception as exc:
                name = type(exc).__name__
                kind = (
                    "ambiguous"
                    if name == "AmbiguousTimeError"
                    else ("nonexistent" if name == "NonExistentTimeError" else "invalid")
                )
                cache[value] = (None, kind)
        timestamp, failure = cache[value]
        parsed.append(timestamp)
        if failure:
            failures[failure].append(index)
    return parsed, failures


def normalize_events(
    source: pd.DataFrame,
    canonical: dict[str, list[Any]],
    parsed_times: dict[str, list[pd.Timestamp | None]],
    source_event_order: list[int | None],
) -> pd.DataFrame:
    """Keep every source row, then order by case, instant, explicit order, and source row."""
    result = pd.DataFrame(canonical)
    result["source_row"] = list(range(1, len(source) + 1))
    result["source_event_order"] = pd.Series(source_event_order, dtype=object)
    result["case_key"] = [
        json.dumps([process, case], ensure_ascii=False, separators=(",", ":"))
        for process, case in zip(result["process_type"], result["case_id"], strict=True)
    ]
    result["attributes"] = [
        {column: source_value(value) for column, value in zip(source.columns, row, strict=True)}
        for row in source.itertuples(index=False, name=None)
    ]
    result["_time"] = pd.to_datetime(parsed_times["timestamp"], utc=True)
    result["_tie"] = pd.Series(source_event_order, dtype="Int64")
    for field, timestamps in parsed_times.items():
        result[field] = [
            timestamp.isoformat() if timestamp is not None else None for timestamp in timestamps
        ]
    result = result.sort_values(
        ["process_type", "case_id", "_time", "_tie", "source_row"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)
    result["event_order"] = result.groupby("case_key", sort=False).cumcount() + 1
    return (
        result.drop(columns=["_time", "_tie"])
        .astype(object)
        .where(pd.notna(result.drop(columns=["_time", "_tie"])), None)
    )
