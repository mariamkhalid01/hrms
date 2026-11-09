"""Synchronous worker-thread operations preparing uploaded data for later analysis."""

import os
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import uuid4

from app.core.config import Settings
from app.schemas.datasets import DatasetPreview, MappingRequest, ProcessRequest, ReadyDataset
from app.services.ingestion.csv_reader import inspect_csv, read_frame
from app.services.ingestion.errors import DatasetError
from app.services.ingestion.storage import DatasetStore, digest
from app.services.mapping.mapper import suggest_mapping
from app.services.process_separation.separator import summarize_processes
from app.services.validation.engine import validate_and_normalize


def now() -> str:
    return datetime.now(UTC).isoformat()


class DatasetService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = DatasetStore(settings.dataset_storage_dir)

    def upload(self, filename: str | None, file: BinaryIO) -> dict:
        name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        if not name or not name.lower().endswith(".csv"):
            raise DatasetError(
                400, "INVALID_FILE_EXTENSION", "Choose a file with a .csv extension."
            )
        if len(name) > 255:
            raise DatasetError(400, "INVALID_FILENAME", "Use a filename of at most 255 characters.")
        identifier, directory = self.store.create()
        try:
            size = 0
            with (directory / "source.csv").open("wb") as target:
                for chunk in iter(lambda: file.read(1_048_576), b""):
                    size += len(chunk)
                    if size > self.settings.max_upload_bytes:
                        raise DatasetError(
                            413, "UPLOAD_TOO_LARGE", "The CSV exceeds the allowed file size."
                        )
                    target.write(chunk)
            if size == 0:
                raise DatasetError(400, "EMPTY_CSV", "The uploaded file is empty.")
            description = inspect_csv(directory / "source.csv", self.settings)
            metadata = {
                "id": identifier,
                "filename": name,
                "size_bytes": size,
                **description,
                "suggested_mapping": suggest_mapping([c["name"] for c in description["columns"]]),
                "status": "uploaded",
                "created_at": now(),
                "source_sha256": digest(directory / "source.csv"),
            }
            # Assert the response contract before committing an accepted upload.
            preview = DatasetPreview.model_validate(metadata).model_dump()
            self.store.write(identifier, "metadata.json", metadata)
            return preview
        except BaseException:
            self.store.discard(identifier)
            raise

    def preview(self, dataset_id: str) -> dict:
        with self.store.lock(dataset_id):
            return DatasetPreview.model_validate(self.store.read(dataset_id)).model_dump()

    def _source(self, dataset_id: str, metadata: dict):
        path = self.store.path(dataset_id) / "source.csv"
        if not path.is_file() or digest(path) != metadata["source_sha256"]:
            raise DatasetError(
                409, "SOURCE_CHANGED", "The stored source file changed. Upload the CSV again."
            )
        return read_frame(path, metadata)

    def validate(self, dataset_id: str, request: MappingRequest) -> dict:
        with self.store.lock(dataset_id):
            metadata = self.store.read(dataset_id)
            frame = self._source(dataset_id, metadata)
            body, _normalized = validate_and_normalize(frame, **request.model_dump())
            identifier = str(uuid4())
            report = {**body, "validation_id": identifier, "dataset_id": dataset_id}
            revision = {
                "validation_id": identifier,
                "request": request.model_dump(),
                "report": report,
                "source_sha256": metadata["source_sha256"],
            }
            # Write revision first; it is authoritative if interrupted between atomic commits.
            self.store.write(dataset_id, "validation.json", revision)
            metadata.update(status="validated" if body["valid"] else "uploaded")
            metadata.pop("processed_validation_id", None)
            self.store.write(dataset_id, "metadata.json", metadata)
            return report

    def process(self, dataset_id: str, request: ProcessRequest, progress=None, force=False) -> dict:
        with self.store.lock(dataset_id):
            metadata = self.store.read(dataset_id)
            revision_path = self.store.path(dataset_id) / "validation.json"
            if not revision_path.is_file():
                raise DatasetError(409, "VALIDATION_REQUIRED", "Validate the column mapping first.")
            revision = self.store.read(dataset_id, "validation.json")
            if request.validation_id != revision["validation_id"]:
                raise DatasetError(
                    409,
                    "STALE_VALIDATION",
                    "The mapping changed. Use the latest validation report.",
                )
            report = revision["report"]
            if not report["valid"]:
                raise DatasetError(
                    409, "VALIDATION_FAILED", "Resolve validation errors before processing."
                )
            if metadata.get("processed_validation_id") == request.validation_id and not force:
                return self.store.read(dataset_id, "result.json")
            if report["summary"]["warning_count"] and not request.acknowledge_warnings:
                raise DatasetError(
                    409, "WARNINGS_NOT_ACKNOWLEDGED", "Review and acknowledge the warnings first."
                )
            if progress:
                progress("reading_dataset")
            frame = self._source(dataset_id, metadata)
            if progress:
                progress("validating_event_log")
            checked, normalized = validate_and_normalize(
                frame,
                **revision["request"],
                on_normalize=(lambda: progress("normalizing_data")) if progress else None,
            )
            if not checked["valid"] or normalized is None:
                raise DatasetError(
                    409,
                    "VALIDATION_CHANGED",
                    "The data no longer passes validation. Validate it again.",
                )
            directory = self.store.path(dataset_id)
            temporary = directory / f".normalized.{uuid4().hex}.tmp"
            try:
                with temporary.open("w", encoding="utf-8", newline="\n") as written:
                    normalized.to_json(written, orient="records", lines=True, force_ascii=False)
                    written.flush()
                    os.fsync(written.fileno())
                os.replace(temporary, directory / "normalized.jsonl")
            finally:
                temporary.unlink(missing_ok=True)
            if progress:
                progress("separating_processes")
            processes = summarize_processes(normalized)
            result = ReadyDataset(
                dataset_id=dataset_id,
                status="ready",
                filename=metadata["filename"],
                event_count=len(normalized),
                case_count=int(normalized["case_key"].nunique()),
                process_count=len(processes),
                processes=processes,
                processed_at=now(),
                normalization={
                    "timezone": "UTC",
                    "source_timezone": checked["source_timezone"],
                    "sorted_by": [
                        "process_type",
                        "case_id",
                        "timestamp",
                        "source_event_order",
                        "source_row",
                    ],
                    "preserved_source": True,
                },
            ).model_dump()
            self.store.write(dataset_id, "result.json", result)
            metadata.update(
                status="ready",
                processed_validation_id=request.validation_id,
                normalized_sha256=digest(directory / "normalized.jsonl"),
            )
            self.store.write(dataset_id, "metadata.json", metadata)
            return result

    def result(self, dataset_id: str) -> dict:
        with self.store.lock(dataset_id):
            metadata = self.store.read(dataset_id)
            if metadata["status"] != "ready":
                raise DatasetError(
                    409, "DATASET_NOT_READY", "Process a valid mapping before requesting results."
                )
            revision = self.store.read(dataset_id, "validation.json")
            if metadata.get("processed_validation_id") != revision["validation_id"]:
                raise DatasetError(
                    409,
                    "STALE_VALIDATION",
                    "The mapping changed. Process the latest validated revision.",
                )
            return self.store.read(dataset_id, "result.json")
