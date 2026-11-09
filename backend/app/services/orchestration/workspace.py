"""Current-analysis recommendations and case timelines without returning unbounded logs."""

import json
from collections import OrderedDict
from threading import RLock

import pandas as pd

from app.schemas.discovery import DiscoveryRequest
from app.schemas.workspace import CaseDetail, CasePage, RecommendationPage
from app.services.ingestion.errors import DatasetError
from app.services.orchestration.analytics import AnalyticsService


class WorkspaceService:
    def __init__(self, analytics: AnalyticsService) -> None:
        self.analytics = analytics
        self.store = analytics.store
        self._case_cache = OrderedDict()
        self._cache_guard = RLock()

    def prepare_recommendations(self, dataset_id: str) -> dict:
        from app.services.recommendations.engine import recommend

        with self.store.lock(dataset_id):
            analysis = self.analytics._read_current(dataset_id)
            path = self.store.path(dataset_id) / "recommendations.json"
            if path.is_file():
                cached = self.store.read(dataset_id, "recommendations.json")
                if cached["analysis_id"] == analysis["analysis_id"]:
                    return cached
            result = {
                "analysis_id": analysis["analysis_id"],
                "items": recommend(analysis["findings"]),
            }
            self.store.write(dataset_id, "recommendations.json", result)
            return result

    def recommendations(self, dataset_id: str, offset: int, limit: int, process_id=None) -> dict:
        with self.store.lock(dataset_id):
            analysis = self.analytics._read_current(dataset_id)
            if process_id:
                self.analytics._process(analysis, process_id)
            result = self.prepare_recommendations(dataset_id)
            items = [
                item
                for item in result["items"]
                if not process_id or item["process_id"] == process_id
            ]
            return RecommendationPage(
                analysis_id=result["analysis_id"],
                total=len(items),
                offset=offset,
                limit=limit,
                items=items[offset : offset + limit],
            ).model_dump()

    def _cases(self, dataset_id: str):
        from app.services.discovery.log import build_log, prepare_frame, stable_id

        mined = self.analytics.discovery._read_current(dataset_id)
        key = (dataset_id, mined["analysis_id"])
        with self._cache_guard:
            if key in self._case_cache:
                self._case_cache.move_to_end(key)
                return mined, self._case_cache[key]
        with (self.store.path(dataset_id) / "normalized.jsonl").open(encoding="utf-8") as source:
            records = [json.loads(line) for line in source if line.strip()]
        originals = {record["source_row"]: record for record in records}
        options = DiscoveryRequest.model_validate(mined["configuration"])
        frame = prepare_frame(pd.DataFrame(records), options)
        _, cases = build_log(frame, options)
        indexed = {}
        for case in cases:
            first = case.records[0]
            sequence = [record["activity"] for record in case.records]
            identifier = stable_id("case", first["process_type"], first["case_id"])
            indexed[identifier] = {
                "summary": {
                    "id": identifier,
                    "case_id": first["case_id"],
                    "process_id": stable_id("process", first["process_type"]),
                    "process_type": first["process_type"],
                    "variant_id": stable_id("variant", first["process_type"], sequence),
                    "event_count": len(case.records),
                    "observed_duration_seconds": case.duration,
                    "status": case.state,
                },
                "events": [originals[record["source_row"]] for record in case.records],
            }
        with self._cache_guard:
            self._case_cache[key] = indexed
            # Bound the cache; authoritative file hashes are checked on every read.
            while len(self._case_cache) > 2:
                self._case_cache.popitem(last=False)
        return mined, indexed

    def cases(self, dataset_id, offset, limit, process_id=None, variant_id=None, search=None):
        with self.store.lock(dataset_id):
            mined, indexed = self._cases(dataset_id)
            if process_id and not any(model["id"] == process_id for model in mined["processes"]):
                raise DatasetError(404, "PROCESS_NOT_FOUND", "This process is not in the dataset.")
            items = [
                item["summary"]
                for item in indexed.values()
                if (not process_id or item["summary"]["process_id"] == process_id)
                and (not variant_id or item["summary"]["variant_id"] == variant_id)
                and (not search or search.casefold() in item["summary"]["case_id"].casefold())
            ]
            return CasePage(
                analysis_id=mined["analysis_id"],
                total=len(items),
                offset=offset,
                limit=limit,
                items=items[offset : offset + limit],
            ).model_dump()

    def case(self, dataset_id, case_id, offset, limit):
        with self.store.lock(dataset_id):
            mined, indexed = self._cases(dataset_id)
            if case_id not in indexed:
                raise DatasetError(404, "CASE_NOT_FOUND", "This case is not in the dataset.")
            item = indexed[case_id]
            return CaseDetail(
                analysis_id=mined["analysis_id"],
                case=item["summary"],
                total_events=len(item["events"]),
                offset=offset,
                limit=limit,
                events=item["events"][offset : offset + limit],
            ).model_dump()
