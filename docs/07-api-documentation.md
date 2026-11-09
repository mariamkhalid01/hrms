# 7 API documentation

## 7.1 Contract conventions

The local backend origin is `http://127.0.0.1:8000`; application routes have prefix `/api/v1`. This inventory was checked against the running server's OpenAPI document on 9 November 2026 and the route/service implementation. It contains 22 application operations. Interactive Swagger documentation is served by `GET /api/docs`, and the machine-readable specification by `GET /api/openapi.json`. A captured [OpenAPI specification](reference/openapi.json) accompanies this documentation. ReDoc is disabled.

For readability below, `D` means the complete dataset path `/api/v1/datasets/{dataset_id}`. Every `D/...` path must be expanded with that prefix. A dataset ID is a UUID returned by upload; a job ID is a UUID returned by job creation. Process, variant, entity and case tokens are opaque strings returned by the relevant result, not activity labels or source business IDs. Invalid UUID syntax and invalid query/body values return HTTP 422. There is no login or authorization contract in the current local application.

JSON requests use `Content-Type: application/json`. Upload uses `multipart/form-data` with a single required field named `file`; the browser supplies its multipart boundary. GET operations have no request body. Unless otherwise stated, a successful operation returns HTTP 200. List endpoints use `offset` (integer, default 0, minimum 0) and `limit` (integer, range 1–200, default 50). Case-event detail defaults to 100 events. Pagination is explicit; responses do not imply that all records have been returned.

## 7.2 Shared request contracts

### MappingRequest

Required `mapping` is an object from canonical field names to source column names or null. Required canonical mappings are `case_id`, `activity`, and `timestamp`. Optional `timezone` defaults to `UTC` and has length 1–100; `timestamp_format` is nullable text of at most 200 characters; `day_first` defaults to false. Unsupported top-level properties are rejected. Semantic mapping errors are reported in a successful HTTP 200 validation report with `valid: false`; this is distinct from malformed request JSON returning 422.

```json
{
  "mapping": {
    "case_id": "Request number",
    "activity": "Step",
    "timestamp": "Finished at",
    "process_type": "Workflow"
  },
  "timezone": "Africa/Cairo",
  "timestamp_format": null,
  "day_first": false
}
```

This is an illustrative request shape; the source column names must actually exist in the uploaded file.

### ProcessRequest

Required `validation_id` is nonempty text of at most 100 characters. Optional `acknowledge_warnings` defaults to false. Preparation uses the latest saved validation revision, rejects blocking errors, and requires acknowledgement of warnings. This endpoint prepares the log; it does not itself run mining or analytics.

### DiscoveryRequest

All fields have defaults: `algorithm` is `auto`, `dfg`, or `inductive` (default `auto`); `noise_threshold` is a number from 0 inclusive to 1 exclusive (default 0). Nonzero noise is invalid with `dfg`. Optional `case_status_attribute` is nonempty text up to 200 characters, paired with `case_status_values`, a dictionary of at most 100 original value strings mapped to `completed`, `incomplete`, `cancelled`, or `unknown`. Both status settings must be supplied together. Source keys must be nonempty and unique after trimming and case folding. Unknown case-status attributes return 422. An empty JSON object is a valid default discovery request.

### AnalyticsRequest and thresholds

Optional `discovery` contains a DiscoveryRequest. `thresholds` contains the default screening configuration; `process_overrides` maps exact process names to partial threshold settings, with at most 200 process entries. Explicit per-process settings replace corresponding global settings. Unknown process names, activity labels or transition IDs are rejected. Defaults are screening rules, not empirically established HR service standards.

| Threshold field | Default | Accepted values or meaning |
| --- | --- | --- |
| `minimum_samples` | 5 | Integer 3–1000. |
| `minimum_affected_cases` | 2 | Integer 1–1000. |
| `iqr_multiplier` | 1.5 | Number 0.5–10. |
| `minimum_relative_increase` | 2 | Number 1–10. |
| `processing_seconds` | null | Optional finite nonnegative business threshold. |
| `waiting_seconds` | null | Optional finite nonnegative business threshold. |
| `case_duration_seconds` | null | Optional finite nonnegative business threshold. |
| `handovers_per_case` | null | Optional finite nonnegative threshold. |
| `repeated_case_percentage` | 20 | Number 0–100. |
| `variant_repetition_percentage` | 20 | Number 0–100. |
| `processing_seconds_by_activity` | Empty object | At most 200 existing activity labels to finite nonnegative seconds. |
| `waiting_seconds_by_transition` | Empty object | At most 500 existing transition IDs to finite nonnegative seconds. |

### AnalysisJobRequest

Optional `validation_id` identifies the current revision; if omitted, the latest revision is used. `acknowledge_warnings` defaults to false. Optional `analytics` contains AnalyticsRequest. When options are omitted, a previous saved analytics/discovery configuration may be reused; otherwise defaults apply. A previously confirmed current revision satisfies warning acknowledgement when rerunning. Starting a second job for an already-active dataset returns its existing job. At most eight datasets may have active or queued jobs, with one worker executing them.

```json
{
  "validation_id": "<latest validation ID>",
  "acknowledge_warnings": true,
  "analytics": {
    "discovery": {
      "algorithm": "auto",
      "case_status_attribute": "case_status",
      "case_status_values": {
        "Completed": "completed",
        "Rejected": "completed",
        "Incomplete": "incomplete",
        "Cancelled": "cancelled"
      }
    }
  }
}
```

This example is appropriate only when the uploaded source actually contains those case-status values and rejection represents a closed case. Status interpretation is a user decision, not an automatic HR assumption.

## 7.3 Response contracts

The following summaries name the actual Pydantic contracts. The accompanying OpenAPI file contains their full nested schemas, required properties and enum values.

| Contract | Response structure |
| --- | --- |
| `HealthResponse` | `status`, `service`, `version`, `environment`. |
| `UploadConfig` | `max_upload_bytes`, `max_rows`, `max_columns`, `preview_rows`. |
| `DatasetPreview` | `id`, filename/size/row/column totals, columns with inferred type and missing/unique statistics, bounded preview records, suggested mapping, delimiter, encoding, status and creation time. |
| `ValidationReport` | `validation_id`, `dataset_id`, `valid`, summary counts, issues, up to ten normalized preview rows, UTC timezone and source timezone. Each issue supplies code, severity, explanation, resolution, affected count, and up to ten row numbers and distinct sample values. |
| `ReadyDataset` | Dataset ID, `status: ready`, filename, event/case/process totals, process summaries, processing time, and normalization timezone/order/source-preservation metadata. |
| `DiscoveryResult` | Schema version `1.0`, dataset/analysis/validation IDs, normalized hash, creation time, elapsed computation milliseconds, PM4Py version, configuration, counts and process models. |
| `ProcessModel` | Stable ID/name/counts, activities, transitions, observed start/end activities, alternative paths, loop groups, React Flow nodes/edges, inductive status/tree/Petri net, and interpretation metadata. Raw PM4Py objects are never returned. |
| `VariantPage` | Analysis/process IDs, `total`, `offset`, `limit`, and items containing sequence and activity IDs, case count/share, mean/median observed duration, duration distributions and status counts. |
| `AnalyticsResult` | Schema version, IDs and hash, creation/computation times, configuration, total cases/events/processes/findings, overall case-duration distribution, process metrics and explicit metric semantics. Findings and variants have separate paginated routes. |
| `ProcessPerformance` | Case/event totals; observed, completed and full-interval duration distributions; completion coverage/rates; processing and waiting metrics; repetition/variant totals; activity/transition metrics; nullable resource/department analyses; effective thresholds, finding counts and warnings. |
| `PerformanceVariantsPage` | Analysis/process IDs and pagination; items with exact sequence, count/share, duration distribution, repeated-activity count, extra-event percentage and case states. |
| `FindingsPage` | Analysis ID and pagination; findings with process/entity identity, category, metric/unit/measurement type, observed value, baseline, affected cases, severity, evidence, potential impact and `cause_status: not_established`. |
| `AnalysisJob` | Job/dataset IDs, status, current stage, ordered stage records with status/timestamps/detail, creation/update time, nullable error and resulting discovery/analytics analysis IDs. |
| `RecommendationPage` | Analysis ID and pagination; items with title, priority, target, finding IDs, evidence summary, actions, measurement plan, caveats, affected cases and `expected_improvement: null`. |
| `CasePage` | Discovery analysis ID and pagination; case token, source case ID, process/variant IDs, event count, observed duration and case status for each item. |
| `CaseDetail` | Discovery analysis ID, case summary, `total_events`, pagination and normalized events including original `attributes`. |

A duration distribution has `count`, `mean`, `median`, `minimum`, and `maximum`; statistics are null when the distribution is empty. Waiting metrics separate measured intervals, timestamp-based approximations, signed interval gaps, interval/approximation counts and overlaps. All duration values are seconds unless the field explicitly says milliseconds. Dataset/analysis timestamps are ISO 8601 UTC values.

## 7.4 Endpoint inventory

The named error groups in each endpoint entry are defined in Section 7.5. All endpoints can also return general request or server errors.

### API-01 Health

`GET /api/v1/health`

Purpose: liveness and configuration identity without loading data or PM4Py. Parameters/body: none. Response: HealthResponse. Errors: general errors only. Observed development response:

```json
{"status":"ok","service":"hr-process-mining-api","version":"0.1.0","environment":"development"}
```

### API-02 Upload configuration

`GET /api/v1/datasets/config`

Purpose: obtain limits for client validation. Parameters/body: none. Response: UploadConfig. Errors: general errors. Default configuration is 52,428,800 bytes, 250,000 data rows, 200 columns and 20 preview rows; environment configuration may lower these limits.

### API-03 Upload event log

`POST /api/v1/datasets/upload`

Purpose: store and inspect one CSV. Request: required multipart `file`; no path/query parameters. Response: HTTP 201 DatasetPreview. Errors: upload group. Example invocation: `curl.exe -F "file=@event_log.csv" http://127.0.0.1:8000/api/v1/datasets/upload`. This creates a dataset but does not automatically analyze it.

### API-04 Read preview

`GET D`

Purpose: retrieve saved upload metadata and preview. Required path: dataset UUID. Body/query: none. Response: DatasetPreview. Errors: storage group. Status is `uploaded`, `validated`, or `ready`; it does not describe analysis-job completion.

### API-05 Validate mapping

`POST D/validate`

Purpose: validate mapped source data and generate a new revision. Required path: dataset UUID. Required JSON body: MappingRequest. Response: ValidationReport, including blocking data issues at HTTP 200. Errors: storage group and 409 `SOURCE_CHANGED`; malformed request values return 422. Revalidation invalidates the prior preparation revision and its downstream result currency.

### API-06 Prepare normalized log

`POST D/process`

Purpose: confirm a valid revision, normalize events and summarize process partitions. Required path: dataset UUID. Required JSON body: ProcessRequest. Response: ReadyDataset. Errors: storage and preparation groups. This lower-level route can be used by API clients; the frontend's complete workflow uses the background analysis job route.

### API-07 Read preparation result

`GET D/result`

Purpose: retrieve the current prepared dataset summary. Required path: dataset UUID. Body/query: none. Response: ReadyDataset. Errors: storage group, 409 `DATASET_NOT_READY` or `STALE_VALIDATION`.

### API-08 Run discovery

`POST D/discovery`

Purpose: discover each process from the normalized log; reuse a matching current result when available. Required path: dataset UUID. Required JSON body: DiscoveryRequest (`{}` is valid). Response: DiscoveryResult. Errors: storage, preparation/readiness and discovery groups; 422 `UNKNOWN_CASE_STATUS_ATTRIBUTE`. This synchronous route runs in a worker thread and may return 429 when discovery capacity is occupied.

### API-09 Read discovery result

`GET D/discovery`

Purpose: retrieve current process models. Required path: dataset UUID. Body/query: none. Response: DiscoveryResult. Errors: storage, preparation/readiness and discovery-read groups.

### API-10 Read one process model

`GET D/discovery/processes/{process_id}`

Purpose: retrieve the discovered model for one process. Required paths: dataset UUID and process token. Body/query: none. Response: ProcessModel. Errors: discovery-read groups and 404 `PROCESS_NOT_FOUND`.

### API-11 Read discovered variants

`GET D/discovery/processes/{process_id}/variants`

Purpose: inspect exact case sequences with discovery statistics. Required paths: dataset UUID and process token. Optional query: `offset`, `limit`. Body: none. Response: VariantPage. Errors: discovery-read groups and 404 `PROCESS_NOT_FOUND`.

### API-12 Run analytics

`POST D/analytics`

Purpose: calculate metrics and findings, running default discovery if no current discovery exists. Required path: dataset UUID. Required JSON body: AnalyticsRequest (`{}` is valid). An explicitly supplied discovery configuration first runs or reuses that discovery. Response: AnalyticsResult. Errors: storage, preparation/readiness, discovery and analytics groups. Matching current configuration/results can be reused.

### API-13 Read analytics

`GET D/analytics`

Purpose: retrieve current dataset and process metrics. Required path: dataset UUID. Body/query: none. Response: AnalyticsResult. Errors: analytics-read groups.

### API-14 Read one process's metrics

`GET D/analytics/processes/{process_id}`

Purpose: obtain detailed performance and assignment analysis for a process. Required paths: dataset UUID and process token. Body/query: none. Response: ProcessPerformance. Errors: analytics-read groups and 404 `PROCESS_NOT_FOUND`.

### API-15 Read variant performance

`GET D/analytics/processes/{process_id}/variants`

Purpose: retrieve duration and repetition comparisons for actual sequences. Required paths: dataset UUID and process token. Optional query: `offset`, `limit`. Body: none. Response: PerformanceVariantsPage. Errors: analytics-read groups and 404 `PROCESS_NOT_FOUND`.

### API-16 Filter findings

`GET D/analytics/findings`

Purpose: inspect measured findings and their supporting evidence. Required path: dataset UUID. Optional query: `offset`, `limit`, `process_id`, `entity_id`, `severity` (`low`, `medium`, `high`), and `category` (`long_processing`, `long_waiting`, `repeated_activity`, `rework_path`, `delayed_cases`, `slow_variant`, `frequent_handovers`, `workload_imbalance`). Body: none. Response: FindingsPage. Errors: analytics-read groups, 404 for an unknown process, or 422 for invalid enums/pagination. An unmatched entity filter returns an empty page.

### API-17 Start full analysis

`POST D/analysis-jobs`

Purpose: execute validation/preparation, discovery, analytics, bottlenecks and recommendations with observable stages. Required path: dataset UUID. Required JSON body: AnalysisJobRequest (`{}` uses the latest saved validation and applicable defaults). Response: HTTP 202 AnalysisJob, initially queued or an existing active job. Errors: storage, preparation and job-start groups. Later computation failures are persisted in the job's `error` field rather than changing the already-returned 202 response.

### API-18 Read latest job

`GET D/analysis-jobs/latest`

Purpose: resume polling the latest job for the selected dataset. Required path: dataset UUID. Body/query: none. Response: AnalysisJob. Errors: 404 `DATASET_NOT_FOUND` or `ANALYSIS_JOB_NOT_FOUND`. An interrupted queued/running job from an earlier server lifetime is returned as failed with `ANALYSIS_INTERRUPTED`.

### API-19 Read a job

`GET D/analysis-jobs/{job_id}`

Purpose: poll a particular job's actual stages. Required paths: dataset UUID and job UUID. Body/query: none. Response: AnalysisJob. Errors: storage group; a missing job file currently uses 404 `DATASET_NOT_FOUND`. Restart interruption is represented inside a successful job response as described above.

### API-20 Read recommendations

`GET D/recommendations`

Purpose: retrieve recommendations linked to current findings. Required path: dataset UUID. Optional query: `offset`, `limit`, `process_id`. Body: none. Response: RecommendationPage. Errors: analytics-read groups and 404 `PROCESS_NOT_FOUND`. If current recommendations are not cached, this GET computes and persists them from current findings. It never applies an operational change.

### API-21 Find cases

`GET D/cases`

Purpose: search cases in the current discovered log. Required path: dataset UUID. Optional query: `offset`, `limit`, `process_id`, `variant_id`, and `search` (at most 200 characters; case-insensitive substring of source case ID). Body: none. Response: CasePage. Errors: discovery-read groups and 404 `PROCESS_NOT_FOUND`. An unmatched variant or search returns an empty page.

### API-22 Read a case timeline

`GET D/cases/{case_id}`

Purpose: inspect canonical events and original attributes for one case. Required paths: dataset UUID and the stable case token from CasePage. Optional query: `offset`, `limit` (default 100). Body: none. Response: CaseDetail. Errors: discovery-read groups and 404 `CASE_NOT_FOUND`. Supplying the displayed source case ID instead of the token will not identify the case.

## 7.5 Errors and recovery

Error responses use `{"error":{"code":"...","message":"...","request_id":"...","details":[...]}}`; `details` is optional and used for request-validation locations/messages/types. `X-Request-ID` is also returned as a header. A valid UUID supplied in that request header is retained; otherwise the server generates one. Unhandled errors return sanitized `INTERNAL_ERROR` text instead of internal exception details. The groups below define endpoint-specific errors referenced in Section 7.4.

| Group | HTTP status and implemented codes | Recovery |
| --- | --- | --- |
| General | 422 `VALIDATION_ERROR`; 404 `NOT_FOUND`; 405 `METHOD_NOT_ALLOWED`; other HTTP errors `HTTP_ERROR`; 500 `INTERNAL_ERROR`. | Correct route, method or request fields; use the request ID to investigate unexpected failure. |
| Upload | 400 `INVALID_FILE_EXTENSION`, `INVALID_FILENAME`, `EMPTY_CSV`, `BINARY_FILE`, `INVALID_HEADERS`, `DUPLICATE_HEADERS`, `MALFORMED_CSV`; 413 `UPLOAD_TOO_LARGE`, `TOO_MANY_ROWS`, `TOO_MANY_COLUMNS`; 415 `UNSUPPORTED_ENCODING`. | Provide a rectangular supported CSV with a header and event rows within configured limits. UTF-8 and BOM-marked UTF-16 are supported. |
| Storage | 404 `DATASET_NOT_FOUND`. | Select or upload an existing dataset; verify the returned UUID. |
| Preparation and readiness | 409 `VALIDATION_REQUIRED`, `STALE_VALIDATION`, `VALIDATION_FAILED`, `WARNINGS_NOT_ACKNOWLEDGED`, `SOURCE_CHANGED`, `VALIDATION_CHANGED`, `DATASET_NOT_READY`. | Revalidate/correct mapping, acknowledge warnings, prepare the current revision, or upload the original source again as directed. |
| Discovery read | Storage/readiness errors; 404 `DISCOVERY_NOT_FOUND`; 409 `NORMALIZED_LOG_MISSING`, `NORMALIZED_LOG_CHANGED`, `STALE_DISCOVERY`. | Prepare and discover the current immutable source revision again. |
| Discovery computation | Discovery-read/preparation errors; 409 `INVALID_NORMALIZED_LOG`; 422 `UNKNOWN_CASE_STATUS_ATTRIBUTE`; 429 `DISCOVERY_BUSY`. | Correct case-status configuration or repeat preparation; retry after occupied capacity becomes available. |
| Analytics read | Discovery-read errors; 404 `ANALYTICS_NOT_FOUND`; 409 `STALE_ANALYTICS`. | Calculate analytics for the current discovery result. |
| Analytics computation | Discovery/preparation errors; 422 `UNKNOWN_THRESHOLD_PROCESS`, `UNKNOWN_THRESHOLD_TARGET`; 429 `ANALYTICS_BUSY`; 409 `STALE_ANALYTICS`. | Use exact process names/activity labels/transition IDs and retry after competing analysis finishes. |
| Job start | Storage/preparation errors; 429 `JOB_QUEUE_FULL`. | Correct the saved validation or retry when the bounded queue has capacity. |

Application-level CSV validation issues are not HTTP errors. A `ValidationReport` separates `error`, `warning` and `info`; `valid` is false only when blocking errors exist. Summary error/warning/info counts count issue categories, not individual affected rows. Each issue separately contains its affected record count and bounded examples.

Job states are `queued`, `running`, `completed`, or `failed`; stage states are `pending`, `running`, `completed`, `failed`, or `skipped`. Job error codes can propagate DatasetError codes, use `ANALYSIS_FAILED` for unexpected computation failure, or use `ANALYSIS_INTERRUPTED` after restart. No cancellation or percentage-complete endpoint is implemented.

## 7.6 Client workflow and boundaries

A complete client workflow is: fetch limits; upload; inspect preview; submit mapping; correct any blocking issues; explicitly acknowledge warnings; start an analysis job; poll until completion; read discovery, analytics, findings, recommendations, variants and cases. The standard UI follows this sequence. The separate preparation/discovery/analytics routes support explicit lower-level integration. A ready dataset alone does not mean discovery has been run.

Results are bound to revision IDs, hashes and configuration. Consumers must use returned identifiers and refresh after revalidation or rerunning discovery. The frontend client provides shared network/timeout/error handling, but a network timeout does not prove that a server operation did not run; clients should check the current job/result before repeating work. No dataset catalogue, delete endpoint, authentication, export endpoint, external HR-system connector or expected-model conformance endpoint exists in this route set. Filesystem persistence already exists, but multi-user access control and durable distributed job execution do not.

Implementation sources: [route collection](../backend/app/api/router.py), [dataset routes](../backend/app/api/routes/datasets.py), [discovery routes](../backend/app/api/routes/discovery.py), [analytics routes](../backend/app/api/routes/analytics.py), [workspace routes](../backend/app/api/routes/workspace.py), [request contracts](../backend/app/schemas/datasets.py), [analytics contracts](../backend/app/schemas/analytics.py), [job orchestration](../backend/app/services/orchestration/jobs.py), [workspace reads](../backend/app/services/orchestration/workspace.py), [error handling](../backend/app/core/errors.py), [request middleware](../backend/app/core/middleware.py), and [frontend API client](../frontend/src/lib/api/client.ts).
