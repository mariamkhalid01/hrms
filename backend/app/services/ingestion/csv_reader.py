"""Strict CSV inspection, bounded previews, and string-preserving data reads."""

import csv
import re
from pathlib import Path

import pandas as pd

from app.core.config import Settings
from app.services.ingestion.errors import DatasetError

# At most the configured file limit can be one quoted cell. The process-wide parser
# limit is fixed once at import rather than changed concurrently by requests.
csv.field_size_limit(52_428_800)


def detect_encoding(path: Path) -> str:
    with path.open("rb") as source:
        prefix = source.read(4)
    if prefix.startswith(b"\xff\xfe") or prefix.startswith(b"\xfe\xff"):
        return "utf-16"
    return "utf-8-sig" if prefix.startswith(b"\xef\xbb\xbf") else "utf-8"


def choose_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ""
        counts = {d: len(next(csv.reader([first], delimiter=d), [])) for d in ",;\t|"}
        return max(counts, key=counts.get)


def inferred_type(values: list[str]) -> str:
    if not values:
        return "empty"
    if all(v.lower() in {"true", "false"} for v in values):
        return "boolean"
    # Identifiers with leading zeroes remain visibly text, even in type hints.
    if all(re.fullmatch(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?", v) for v in values):
        return "number"
    if all(re.search(r"\d[-/:]\d", v) for v in values):
        parsed = pd.to_datetime(values, errors="coerce", format="mixed", utc=True)
        if parsed.notna().all():
            return "datetime"
    return "text"


def inspect_csv(path: Path, settings: Settings) -> dict:
    encoding = detect_encoding(path)
    try:
        with path.open("r", encoding=encoding, errors="strict", newline="") as source:
            sample = source.read(65_536)
            if not sample.strip():
                raise DatasetError(
                    400, "EMPTY_CSV", "The CSV is empty. Include a header and events."
                )
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", sample):
                raise DatasetError(
                    400, "BINARY_FILE", "The file contains binary data, not CSV text."
                )
            delimiter = choose_delimiter(sample)
            source.seek(0)
            reader = csv.reader(source, delimiter=delimiter, strict=True)
            columns = next(reader, [])
            if not columns or any(not name.strip() for name in columns):
                raise DatasetError(
                    400, "INVALID_HEADERS", "Every CSV column needs a nonempty header."
                )
            if len(set(columns)) != len(columns):
                raise DatasetError(400, "DUPLICATE_HEADERS", "CSV header names must be unique.")
            if len(columns) > settings.max_columns:
                raise DatasetError(
                    413, "TOO_MANY_COLUMNS", f"Use at most {settings.max_columns} columns."
                )
            missing = [0] * len(columns)
            unique = [set() for _ in columns]
            samples = [[] for _ in columns]
            preview = []
            row_count = 0
            for row_count, row in enumerate(reader, 1):
                if row_count > settings.max_rows:
                    raise DatasetError(
                        413, "TOO_MANY_ROWS", f"Use at most {settings.max_rows} data records."
                    )
                if len(row) != len(columns):
                    raise DatasetError(
                        400,
                        "MALFORMED_CSV",
                        f"Data record {row_count} has {len(row)} fields; expected {len(columns)}. "
                        "Check delimiters and quoted fields.",
                    )
                for index, value in enumerate(row):
                    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
                        raise DatasetError(
                            400, "BINARY_FILE", "The file contains unsupported control bytes."
                        )
                    if not value.strip():
                        missing[index] += 1
                    else:
                        unique[index].add(value)
                        if len(samples[index]) < 500:
                            samples[index].append(value)
                if row_count <= settings.preview_rows:
                    preview.append(
                        {
                            "row_number": row_count,
                            "values": {
                                key: value if value.strip() else None
                                for key, value in zip(columns, row, strict=True)
                            },
                        }
                    )
            if row_count == 0:
                raise DatasetError(400, "EMPTY_CSV", "The CSV has a header but no event records.")
    except UnicodeError as exc:
        raise DatasetError(
            415, "UNSUPPORTED_ENCODING", "Save the CSV as UTF-8 or UTF-16 with a byte-order mark."
        ) from exc
    except csv.Error as exc:
        raise DatasetError(
            400, "MALFORMED_CSV", "The CSV has malformed quoting or oversized fields."
        ) from exc
    return {
        "row_count": row_count,
        "column_count": len(columns),
        "preview": preview,
        "delimiter": delimiter,
        "encoding": encoding,
        "columns": [
            {
                "name": name,
                "inferred_type": inferred_type(samples[i]),
                "missing_count": missing[i],
                "missing_percent": round(missing[i] * 100 / row_count, 2),
                "unique_count": len(unique[i]),
            }
            for i, name in enumerate(columns)
        ],
    }


def read_frame(path: Path, metadata: dict) -> pd.DataFrame:
    # Header, quoting, rectangular rows, encoding and limits were checked on upload.
    return pd.read_csv(
        path,
        sep=metadata["delimiter"],
        encoding=metadata["encoding"],
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        skip_blank_lines=False,
    )
