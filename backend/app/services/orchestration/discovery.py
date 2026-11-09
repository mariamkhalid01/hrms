"""Revision-bound discovery with atomic persistence and bounded worker-thread execution."""

import json
from threading import BoundedSemaphore
from time import perf_counter
from uuid import uuid4

import pandas as pd

from app.schemas.discovery import DiscoveryRequest, DiscoveryResult, VariantPage
from app.services.ingestion.errors import DatasetError
from app.services.ingestion.storage import digest
from app.services.orchestration.datasets import DatasetService, now


class DiscoveryService:
    def __init__(self, datasets: DatasetService) -> None:
        self.datasets = datasets
        self.store = (
            datasets.store
        )  # Share ingestion locks: never mine a partially changed mapping.
        self.capacity = BoundedSemaphore(1)

    def _snapshot(self, dataset_id: str) -> tuple[dict, str]:
        self.datasets.result(dataset_id)
        metadata = self.store.read(dataset_id)
        directory = self.store.path(dataset_id)
        source, normalized = directory / "source.csv", directory / "normalized.jsonl"
        if not source.is_file() or digest(source) != metadata["source_sha256"]:
            raise DatasetError(409, "SOURCE_CHANGED", "The source changed. Upload the CSV again.")
        if not normalized.is_file():
            raise DatasetError(409, "NORMALIZED_LOG_MISSING", "Process the validated log again.")
        fingerprint = digest(normalized)
        if metadata.get("normalized_sha256", fingerprint) != fingerprint:
            raise DatasetError(
                409, "NORMALIZED_LOG_CHANGED", "Upload and process the event log again."
            )
        return metadata, fingerprint

    def run(self, dataset_id: str, options: DiscoveryRequest, force=False) -> dict:
        with self.store.lock(dataset_id):
            metadata, fingerprint = self._snapshot(dataset_id)
            cached_path = self.store.path(dataset_id) / "discovery.json"
            if cached_path.is_file() and not force:
                cached = self.store.read(dataset_id, "discovery.json")
                if (
                    cached["validation_id"] == metadata["processed_validation_id"]
                    and cached["normalized_sha256"] == fingerprint
                    and cached["configuration"] == options.model_dump()
                    and not any(
                        model["inductive"]["status"] == "failed" for model in cached["processes"]
                    )
                ):
                    return DiscoveryResult.model_validate(cached).model_dump()
            if not self.capacity.acquire(blocking=False):
                raise DatasetError(
                    429, "DISCOVERY_BUSY", "Another discovery is running. Retry shortly."
                )
            try:
                # Lazy import: startup and health checks do not load PM4Py or any event log.
                import pm4py

                from app.services.discovery.engine import discover

                started = perf_counter()
                path = self.store.path(dataset_id) / "normalized.jsonl"
                with path.open(encoding="utf-8") as source:
                    frame = pd.DataFrame([json.loads(line) for line in source if line.strip()])
                models, variants = discover(frame, options, self.datasets.settings)
                result = DiscoveryResult(
                    dataset_id=dataset_id,
                    analysis_id=str(uuid4()),
                    validation_id=metadata["processed_validation_id"],
                    normalized_sha256=fingerprint,
                    created_at=now(),
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    pm4py_version=pm4py.__version__,
                    configuration=options,
                    process_count=len(models),
                    event_count=len(frame),
                    case_count=sum(model["case_count"] for model in models),
                    processes=models,
                ).model_dump()
                # Catch external edits during computation as well as ingestion revisions.
                current, current_hash = self._snapshot(dataset_id)
                if (
                    current_hash != fingerprint
                    or current["processed_validation_id"] != metadata["processed_validation_id"]
                ):
                    raise DatasetError(
                        409, "STALE_DISCOVERY", "The dataset changed. Run discovery again."
                    )
                self.store.write(dataset_id, "discovery.json", {**result, "variants": variants})
                return result
            finally:
                self.capacity.release()

    def _read_current(self, dataset_id: str) -> dict:
        metadata, fingerprint = self._snapshot(dataset_id)
        path = self.store.path(dataset_id) / "discovery.json"
        if not path.is_file():
            raise DatasetError(
                404, "DISCOVERY_NOT_FOUND", "Run process discovery for this dataset first."
            )
        result = self.store.read(dataset_id, "discovery.json")
        if (
            result["validation_id"] != metadata["processed_validation_id"]
            or result["normalized_sha256"] != fingerprint
        ):
            raise DatasetError(409, "STALE_DISCOVERY", "The dataset changed. Run discovery again.")
        return result

    def result(self, dataset_id: str) -> dict:
        with self.store.lock(dataset_id):
            return DiscoveryResult.model_validate(self._read_current(dataset_id)).model_dump()

    def process(self, dataset_id: str, process_id: str) -> dict:
        with self.store.lock(dataset_id):
            result = self._read_current(dataset_id)
            for model in result["processes"]:
                if model["id"] == process_id:
                    return model
            raise DatasetError(
                404, "PROCESS_NOT_FOUND", "This process is not in the discovered dataset."
            )

    def variants(self, dataset_id: str, process_id: str, offset: int, limit: int) -> dict:
        with self.store.lock(dataset_id):
            result = self._read_current(dataset_id)
            if process_id not in result["variants"]:
                raise DatasetError(
                    404, "PROCESS_NOT_FOUND", "This process is not in the discovered dataset."
                )
            variants = result["variants"][process_id]
            return VariantPage(
                analysis_id=result["analysis_id"],
                process_id=process_id,
                total=len(variants),
                offset=offset,
                limit=limit,
                items=variants[offset : offset + limit],
            ).model_dump()
