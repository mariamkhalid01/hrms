"""Persist performance results against the exact mined revision and discovery configuration."""

import json
from time import perf_counter
from uuid import uuid4

import pandas as pd

from app.schemas.analytics import (
    AnalyticsRequest,
    AnalyticsResult,
    FindingsPage,
    PerformanceVariantsPage,
)
from app.schemas.discovery import DiscoveryRequest
from app.services.ingestion.errors import DatasetError
from app.services.orchestration.datasets import now
from app.services.orchestration.discovery import DiscoveryService


class AnalyticsService:
    def __init__(self, discovery: DiscoveryService) -> None:
        self.discovery = discovery
        self.store = discovery.store

    def run(self, dataset_id: str, options: AnalyticsRequest, progress=None, force=False) -> dict:
        with self.store.lock(dataset_id):
            if options.discovery is not None:
                self.discovery.run(dataset_id, options.discovery)
            try:
                mined = self.discovery._read_current(dataset_id)
            except DatasetError as exc:
                if exc.code != "DISCOVERY_NOT_FOUND":
                    raise
                self.discovery.run(dataset_id, DiscoveryRequest())
                mined = self.discovery._read_current(dataset_id)
            path = self.store.path(dataset_id) / "analytics.json"
            if path.is_file() and not force:
                cached = self.store.read(dataset_id, "analytics.json")
                if (
                    cached["discovery_analysis_id"] == mined["analysis_id"]
                    and cached["configuration"] == options.model_dump()
                    and "case_duration_seconds" in cached
                ):
                    return AnalyticsResult.model_validate(cached).model_dump()
            # Share mining capacity; discovery above completes before acquiring it for analytics.
            if not self.discovery.capacity.acquire(blocking=False):
                raise DatasetError(
                    429, "ANALYTICS_BUSY", "Another analysis is running. Retry shortly."
                )
            try:
                from app.services.analytics.engine import SEMANTICS, analyze
                from app.services.discovery.log import distribution

                started = perf_counter()
                normalized = self.store.path(dataset_id) / "normalized.jsonl"
                with normalized.open(encoding="utf-8") as source:
                    frame = pd.DataFrame([json.loads(line) for line in source if line.strip()])
                processes, variants, findings = analyze(frame, mined, options, progress)
                instants = pd.to_datetime(frame["timestamp"], utc=True, format="mixed")
                spans = instants.groupby(frame["case_key"]).agg(["min", "max"])
                result = AnalyticsResult(
                    dataset_id=dataset_id,
                    analysis_id=str(uuid4()),
                    discovery_analysis_id=mined["analysis_id"],
                    validation_id=mined["validation_id"],
                    normalized_sha256=mined["normalized_sha256"],
                    created_at=now(),
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    configuration=options,
                    total_cases=mined["case_count"],
                    total_events=mined["event_count"],
                    case_duration_seconds=distribution(
                        (spans["max"] - spans["min"]).dt.total_seconds().tolist()
                    ),
                    process_count=len(processes),
                    finding_count=len(findings),
                    processes=processes,
                    semantics=SEMANTICS,
                ).model_dump()
                current = self.discovery._read_current(dataset_id)
                if current["analysis_id"] != mined["analysis_id"]:
                    raise DatasetError(
                        409, "STALE_ANALYTICS", "Discovery changed. Run analytics again."
                    )
                self.store.write(
                    dataset_id,
                    "analytics.json",
                    {**result, "variants": variants, "findings": findings},
                )
                return result
            finally:
                self.discovery.capacity.release()

    def _read_current(self, dataset_id: str) -> dict:
        mined = self.discovery._read_current(dataset_id)
        if not (self.store.path(dataset_id) / "analytics.json").is_file():
            raise DatasetError(404, "ANALYTICS_NOT_FOUND", "Run performance analytics first.")
        result = self.store.read(dataset_id, "analytics.json")
        if (
            result["discovery_analysis_id"] != mined["analysis_id"]
            or result["normalized_sha256"] != mined["normalized_sha256"]
        ):
            raise DatasetError(409, "STALE_ANALYTICS", "Discovery changed. Run analytics again.")
        return result

    def result(self, dataset_id: str) -> dict:
        with self.store.lock(dataset_id):
            return AnalyticsResult.model_validate(self._read_current(dataset_id)).model_dump()

    @staticmethod
    def _process(result: dict, process_id: str) -> dict:
        for process in result["processes"]:
            if process["id"] == process_id:
                return process
        raise DatasetError(404, "PROCESS_NOT_FOUND", "This process is not in the analyzed dataset.")

    def process(self, dataset_id: str, process_id: str) -> dict:
        with self.store.lock(dataset_id):
            return self._process(self._read_current(dataset_id), process_id)

    def variants(self, dataset_id: str, process_id: str, offset: int, limit: int) -> dict:
        with self.store.lock(dataset_id):
            result = self._read_current(dataset_id)
            self._process(result, process_id)
            items = result["variants"][process_id]
            return PerformanceVariantsPage(
                analysis_id=result["analysis_id"],
                process_id=process_id,
                total=len(items),
                offset=offset,
                limit=limit,
                items=items[offset : offset + limit],
            ).model_dump()

    def findings(
        self,
        dataset_id: str,
        offset: int,
        limit: int,
        process_id=None,
        category=None,
        severity=None,
        entity_id=None,
    ) -> dict:
        with self.store.lock(dataset_id):
            result = self._read_current(dataset_id)
            if process_id is not None:
                self._process(result, process_id)
            items = [
                item
                for item in result["findings"]
                if (process_id is None or item["process_id"] == process_id)
                and (category is None or item["category"] == category)
                and (severity is None or item["severity"] == severity)
                and (entity_id is None or item["entity"]["id"] == entity_id)
            ]
            return FindingsPage(
                analysis_id=result["analysis_id"],
                total=len(items),
                offset=offset,
                limit=limit,
                items=items[offset : offset + limit],
            ).model_dump()
