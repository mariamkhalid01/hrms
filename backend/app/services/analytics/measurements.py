"""Small timing primitives shared by aggregation and evidence rules."""

from dataclasses import dataclass

import pandas as pd

from app.services.discovery.log import distribution


@dataclass(frozen=True)
class Observation:
    value: float
    case_id: str
    rows: tuple[int, ...]


def observe(value: float, *records: dict) -> Observation:
    return Observation(
        float(value),
        str(records[0]["case_id"]),
        tuple(int(record["source_row"]) for record in records),
    )


def summarize(samples: list[Observation]) -> dict:
    return distribution([item.value for item in samples])


def known(value) -> bool:
    return value is not None and not pd.isna(value) and str(value).strip() != ""


def processing(record: dict) -> float | None:
    start, end = record.get("activity_start"), record.get("activity_end")
    return (end - start).total_seconds() if known(start) and known(end) else None


def waiting_summary(gaps: list[Observation], estimates: list[Observation]) -> dict:
    return {
        "measured_wait_seconds": summarize([item for item in gaps if item.value >= 0]),
        "approximate_wait_seconds": summarize(estimates),
        "signed_interval_gap_seconds": summarize(gaps),
        "interval_pair_count": len(gaps),
        "approximation_count": len(estimates),
        "overlap_count": sum(item.value < 0 for item in gaps),
    }
