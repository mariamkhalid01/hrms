"""Observable local background analysis jobs; stages advance only at actual work boundaries."""

import logging
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
from uuid import uuid4

from app.schemas.analytics import AnalyticsRequest
from app.schemas.datasets import ProcessRequest
from app.schemas.discovery import DiscoveryRequest
from app.schemas.workspace import AnalysisJob, AnalysisJobRequest, JobStage
from app.services.ingestion.errors import DatasetError
from app.services.orchestration.datasets import now
from app.services.orchestration.workspace import WorkspaceService

STAGES = [
    ("reading_dataset", "Reading dataset"),
    ("validating_event_log", "Validating event log"),
    ("normalizing_data", "Normalizing data"),
    ("separating_processes", "Separating processes"),
    ("discovering_process_models", "Discovering process models"),
    ("calculating_performance_metrics", "Calculating performance metrics"),
    ("detecting_bottlenecks", "Detecting bottlenecks"),
    ("preparing_recommendations", "Preparing recommendations"),
]


class AnalysisJobService:
    def __init__(self, workspace: WorkspaceService) -> None:
        self.workspace = workspace
        self.analytics = workspace.analytics
        self.discovery = self.analytics.discovery
        self.datasets = self.discovery.datasets
        self.store = workspace.store
        self.guard = RLock()
        self.active: dict[str, str] = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hr-analysis")

    def shutdown(self):
        self.executor.shutdown(wait=True, cancel_futures=True)

    def start(self, dataset_id: str, request: AnalysisJobRequest) -> dict:
        with self.guard:
            if dataset_id in self.active:
                return self.get(dataset_id, self.active[dataset_id])
            if len(self.active) >= 8:
                raise DatasetError(
                    429, "JOB_QUEUE_FULL", "The analysis queue is full. Retry shortly."
                )
            with self.store.lock(dataset_id):
                metadata = self.store.read(dataset_id)
                if not (self.store.path(dataset_id) / "validation.json").is_file():
                    raise DatasetError(
                        409, "VALIDATION_REQUIRED", "Validate and confirm this dataset first."
                    )
                revision = self.store.read(dataset_id, "validation.json")
                if request.validation_id and request.validation_id != revision["validation_id"]:
                    raise DatasetError(409, "STALE_VALIDATION", "Use the latest validated mapping.")
                if not revision["report"]["valid"]:
                    raise DatasetError(
                        409, "VALIDATION_FAILED", "Resolve the validation errors first."
                    )
                already_confirmed = (
                    metadata.get("processed_validation_id") == revision["validation_id"]
                    and metadata.get("status") == "ready"
                )
                if revision["report"]["summary"]["warning_count"] and not (
                    request.acknowledge_warnings or already_confirmed
                ):
                    raise DatasetError(
                        409,
                        "WARNINGS_NOT_ACKNOWLEDGED",
                        "Review and acknowledge the warnings first.",
                    )
                options = request.analytics
                if options is None and (self.store.path(dataset_id) / "analytics.json").is_file():
                    options = AnalyticsRequest.model_validate(
                        self.store.read(dataset_id, "analytics.json")["configuration"]
                    )
                options = options or AnalyticsRequest()
                discovery_options = options.discovery
                if (
                    discovery_options is None
                    and (self.store.path(dataset_id) / "discovery.json").is_file()
                ):
                    discovery_options = DiscoveryRequest.model_validate(
                        self.store.read(dataset_id, "discovery.json")["configuration"]
                    )
                identifier = str(uuid4())
                job = AnalysisJob(
                    id=identifier,
                    dataset_id=dataset_id,
                    status="queued",
                    stages=[JobStage(key=key, label=label) for key, label in STAGES],
                    created_at=now(),
                    updated_at=now(),
                ).model_dump()
                self.store.write(dataset_id, f"job-{identifier}.json", job)
                self.store.write(dataset_id, "job-latest.json", {"id": identifier})
                self.active[dataset_id] = identifier
                response = deepcopy(job)
                self.executor.submit(
                    self._run,
                    job,
                    revision["validation_id"],
                    options,
                    discovery_options or DiscoveryRequest(),
                )
                return response

    def _run(self, job, validation_id, options, discovery_options):
        dataset_id, identifier = job["dataset_id"], job["id"]

        def persist():
            # Serialize Windows reads and atomic replacements of each status file.
            # This short guard is independent of the dataset's long-running computation lock.
            with self.guard:
                job["updated_at"] = now()
                self.store.write(dataset_id, f"job-{identifier}.json", job)

        def progress(key):
            timestamp = now()
            for stage in job["stages"]:
                if stage["status"] == "running" and stage["key"] != key:
                    stage.update(status="completed", completed_at=timestamp)
                if stage["key"] == key:
                    stage.update(status="running", started_at=stage["started_at"] or timestamp)
            job.update(status="running", current_stage=key)
            persist()

        try:
            # One revision is used throughout; polling never takes this dataset lock.
            with self.store.lock(dataset_id):
                self.datasets.process(
                    dataset_id,
                    ProcessRequest(validation_id=validation_id, acknowledge_warnings=True),
                    progress=progress,
                    force=True,
                )
                progress("discovering_process_models")
                mined = self.discovery.run(dataset_id, discovery_options, force=True)
                job["discovery_analysis_id"] = mined["analysis_id"]
                result = self.analytics.run(
                    dataset_id,
                    options.model_copy(update={"discovery": None}),
                    progress=progress,
                    force=True,
                )
                job["analytics_analysis_id"] = result["analysis_id"]
                progress("preparing_recommendations")
                self.workspace.prepare_recommendations(dataset_id)
                job["stages"][-1].update(status="completed", completed_at=now())
                job.update(status="completed", current_stage=None)
                persist()
        except Exception as exc:
            if isinstance(exc, DatasetError):
                error = {"code": exc.code, "message": exc.message}
            else:
                logging.getLogger("hr_process_mining").exception("Background analysis failed")
                error = {
                    "code": "ANALYSIS_FAILED",
                    "message": "Analysis could not finish. Retry or review the event log.",
                }
            for stage in job["stages"]:
                if stage["status"] == "running":
                    stage.update(status="failed", completed_at=now(), detail=error["message"])
            job.update(status="failed", error=error)
            persist()
        finally:
            with self.guard:
                if self.active.get(dataset_id) == identifier:
                    self.active.pop(dataset_id, None)

    def get(self, dataset_id: str, identifier: str) -> dict:
        with self.guard:
            result = self.store.read(dataset_id, f"job-{identifier}.json")
            if (
                result["status"] in {"queued", "running"}
                and self.active.get(dataset_id) != identifier
            ):
                error = {
                    "code": "ANALYSIS_INTERRUPTED",
                    "message": "The server restarted before analysis finished. Run analysis again.",
                }
                result.update(status="failed", error=error, updated_at=now())
                for stage in result["stages"]:
                    if stage["status"] == "running":
                        stage.update(status="failed", detail=error["message"], completed_at=now())
                self.store.write(dataset_id, f"job-{identifier}.json", result)
            return AnalysisJob.model_validate(result).model_dump()

    def latest(self, dataset_id: str) -> dict:
        # A missing latest job is distinct from a missing dataset for client recovery.
        with self.guard:
            if not self.store.path(dataset_id).is_dir():
                raise DatasetError(404, "DATASET_NOT_FOUND", "The dataset was not found.")
            if not (self.store.path(dataset_id) / "job-latest.json").is_file():
                raise DatasetError(404, "ANALYSIS_JOB_NOT_FOUND", "Run analysis to create a job.")
            return self.get(dataset_id, self.store.read(dataset_id, "job-latest.json")["id"])
