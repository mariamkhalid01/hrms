"""Process grouping comes from uploaded data, without a fixed HR process vocabulary."""

import pandas as pd


def split_processes(frame: pd.DataFrame):
    """Yield independent partitions from the explicitly normalized separation field."""
    yield from frame.groupby("process_type", sort=True)


def summarize_processes(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "name": str(name),
            "event_count": len(group),
            "case_count": int(group["case_key"].nunique()),
        }
        for name, group in split_processes(frame)
    ]
