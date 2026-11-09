"""Build explicitly ordered PM4Py traces from canonical records, without source flags."""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from statistics import mean, median

import pandas as pd
from pm4py.objects.log.obj import Event, EventLog, Trace

from app.schemas.discovery import DiscoveryRequest
from app.services.ingestion.errors import DatasetError

STATES = ("completed", "incomplete", "cancelled", "unknown")


def stable_id(kind: str, *parts) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def distribution(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean": float(mean(values)) if values else None,
        "median": float(median(values)) if values else None,
        "minimum": float(min(values)) if values else None,
        "maximum": float(max(values)) if values else None,
    }


@dataclass
class Case:
    key: str
    records: list[dict]
    state: str
    status_conflict: bool
    status_unrecognized: bool

    @property
    def duration(self) -> float:
        return (self.records[-1]["timestamp"] - self.records[0]["timestamp"]).total_seconds()


def case_state(records: list[dict], options: DiscoveryRequest) -> tuple[str, bool, bool]:
    if options.case_status_attribute is None:
        return "unknown", False, False
    values = {
        str(record.get("attributes", {}).get(options.case_status_attribute)).strip().casefold()
        for record in records
        if record.get("attributes", {}).get(options.case_status_attribute) not in (None, "")
    }
    lookup = {key.strip().casefold(): value for key, value in options.case_status_values.items()}
    unknown = any(value not in lookup for value in values)
    states = {lookup.get(value, "unknown") for value in values}
    conflict = len(states) > 1
    # A changing event status must never be interpreted as a trustworthy case status.
    return (next(iter(states)) if len(states) == 1 else "unknown"), conflict, unknown


def prepare_frame(frame: pd.DataFrame, options: DiscoveryRequest) -> pd.DataFrame:
    required = {
        "process_type",
        "case_id",
        "case_key",
        "activity",
        "timestamp",
        "event_order",
        "source_row",
        "attributes",
    }
    if frame.empty or not required.issubset(frame.columns):
        raise DatasetError(409, "INVALID_NORMALIZED_LOG", "Process the validated event log again.")
    result = frame.copy()
    for name in ("timestamp", "activity_start", "activity_end"):
        if name in result:
            result[name] = pd.to_datetime(result[name], utc=True, format="mixed", errors="coerce")
    if result["timestamp"].isna().any():
        raise DatasetError(409, "INVALID_NORMALIZED_LOG", "Normalized timestamps are invalid.")
    if options.case_status_attribute and not any(
        options.case_status_attribute in attributes for attributes in result["attributes"]
    ):
        raise DatasetError(
            422,
            "UNKNOWN_CASE_STATUS_ATTRIBUTE",
            "The selected case-status attribute is not in this dataset.",
        )
    return result.sort_values(
        ["process_type", "case_id", "timestamp", "event_order", "source_row"], kind="stable"
    )


def build_log(frame: pd.DataFrame, options: DiscoveryRequest) -> tuple[EventLog, list[Case]]:
    log = EventLog()
    cases = []
    for key, group in frame.groupby("case_key", sort=False):
        records = group.to_dict(orient="records")
        state, conflict, unrecognized = case_state(records, options)
        case = Case(str(key), records, state, conflict, unrecognized)
        cases.append(case)
        trace = Trace(attributes={"concept:name": str(key), "case_state": state})
        for record in records:
            trace.append(
                Event(
                    {
                        "concept:name": record["activity"],
                        "time:timestamp": record["timestamp"].to_pydatetime(),
                    }
                )
            )
        log.append(trace)
    return log, cases


def state_counts(cases: list[Case]) -> dict[str, int]:
    counts = Counter(case.state for case in cases)
    return {state: counts[state] for state in STATES}
