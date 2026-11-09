# Connected frontend and analysis workflow

The React application displays saved backend results from uploaded event logs. PM4Py discovery, normalization, analytics, finding detection and recommendation generation run in Python. The frontend does not contain a default dataset, predefined HR workflow or simulated analytical result.

## Selection and routes

Opening a fresh application URL without `dataset` starts empty. Uploading and successfully analyzing a CSV deliberately selects it. Navigation carries `?dataset=<dataset UUID>` so refreshing or opening that explicit URL restores the prepared dataset. There is no local-storage selection or last-used fixture fallback. Closing the dataset clears its selection and URL without deleting server files.

The five primary routes are `/overview`, `/process-explorer`, `/bottlenecks`, `/variants` and `/recommendations`. `/cases` supports case-level investigation and `/upload` remains available throughout the workspace. Cross-links use `process`, `entity`, `variant` and `case` query parameters where applicable. These contain returned stable IDs; the backend API names the equivalent filters `process_id`, `entity_id` and `variant_id`.

Overview shows actual totals, pooled case-duration statistics, process comparisons and findings. The workspace uses full-width pages with horizontal navigation and a mobile menu. Process Explorer starts with the most common recorded path and offers all observed paths, using React Flow with step selection, zoom, pan and fit-to-screen. Its rounded task boxes and start/end markers are a visual reading aid, not a claim of a formally discovered BPMN model. Frequency, timing and repetition details remain available on demand.

Bottlenecks presents a spacious list of findings with optional filters and evidence dialogs. The former Variants page is labeled **Process paths**: a path (or variant) is one distinct ordered sequence of activities actually followed by cases. Comparing paths helps identify common routes, additional steps, repetitions and differences in observed duration. It does not establish that a different path is wrong or causes a delay. Path details show the full sequence and link to matching cases.

Case Explorer and Recommendations use full-width lists. Clicking an item opens a focused dialog instead of a permanent right-hand panel. Case dialogs show paginated canonical event timelines and source attributes. Recommendation dialogs show review actions, measurement plans and supporting evidence. Dialogs support keyboard navigation, Escape and focus restoration, and fill the screen on small devices.

## Upload to results

All API paths below are relative to `/api/v1`.

1. Read `/datasets/config`, then `POST /datasets/upload` with the user's CSV. Display the bounded preview and whole-file summary statistics.
2. Let the user review suggested mappings and time interpretation. `POST /datasets/{id}/validate` returns the validation revision and structured errors, warnings and information. Blocking errors require correction; warnings require acknowledgment.
3. Confirm with `POST /datasets/{id}/analysis-jobs`, supplying `validation_id` and `acknowledge_warnings`. The server rejects stale revisions, invalid data or unacknowledged warnings. A successful response is HTTP 202 and a real job record.
4. Poll `/datasets/{id}/analysis-jobs/{job_id}` until completed or failed. Display the reported stage states; there is no estimated progress percentage.
5. Once completed, read `/datasets/{id}/result`, select the prepared dataset, and retrieve `/discovery` and `/analytics`. The frontend checks dataset and analysis IDs against each other and the completed job before displaying results.
6. Fetch bounded findings, variants, recommendations and cases as their pages or filters change. A failed replacement upload leaves the previous active dataset selected. Errors offer a retry rather than substituting sample results.

The preparation-only `POST /datasets/{id}/process` and direct synchronous discovery/analytics APIs remain available. The upload UI uses the full analysis-job endpoint so successful confirmation produces usable analysis pages.

## Background jobs and recovery

`GET /datasets/{id}/analysis-jobs/latest` restores the latest job for an explicitly selected dataset. `GET /datasets/{id}/analysis-jobs/{job_id}` reads a particular job. The job contains its ID, dataset ID, overall status, current stage, stage timestamps/details, any error and the resulting discovery/analytics analysis IDs.

The eight stages advance at actual backend work boundaries:

1. Reading dataset
2. Validating event log
3. Normalizing data
4. Separating processes
5. Discovering process models
6. Calculating performance metrics
7. Detecting bottlenecks
8. Preparing recommendations

Job status is `queued`, `running`, `completed` or `failed`. Stage status is `pending`, `running`, `completed`, `failed` or `skipped`. A short stage may finish between polls; its saved state is still real. An error identifies the failed stage where one was running and leaves later work unfinished.

Starting a job for a dataset already queued/running returns its active job. Otherwise it starts a new full pipeline run. The optional `analytics` request field accepts the existing analytics configuration; omitted settings reuse saved analytics/discovery options when present or use defaults. The frontend follows an existing job, starts one for an explicitly selected prepared dataset with no job, and reruns stale/missing result revisions. A failed job shows an actionable retry.

This is a **local, single-backend-process worker**, with one execution thread and at most eight queued/running datasets. A full queue returns 429 `JOB_QUEUE_FULL`; discovery/analytics also retain their shared computation limits. Stage state is saved to JSON, but execution and the queue are not durable across server restarts. Reading a previously queued/running job after a restart marks it failed with `ANALYSIS_INTERRUPTED`; start analysis again to recover. Closing a browser or aborting a polling request does not cancel backend work. Cancellation and distributed workers are not implemented.

Dataset locks hold one revision through the pipeline. Status polling uses a separate short lock, so it can report progress while that dataset is being analyzed. Completed job IDs identify the exact result versions; a later direct discovery/analytics run can invalidate that match and require a new job. Use one Uvicorn worker with the current file storage. Large logs and graph models still consume server memory; response pagination does not make mining computation streaming.

## Data semantics in the interface

- Each mapped process type is discovered independently. Unknown names and a dataset without a process field work without code changes; the latter becomes one process.
- Case duration is the elapsed span between the first and last observed canonical event timestamp. It includes nights/weekends and is not necessarily full business lead time. The overall average and median come from all observed case spans, not averages of process medians.
- Processing time requires mapped start/end intervals. Nonnegative gaps between consecutive mapped intervals are measured gaps. Consecutive event-timestamp differences are separately labeled waiting-time approximations when interval endpoints are missing. Overlaps are counted separately; missing values remain unavailable.
- Repeated activities and graph cycles are observed behavior. They do not prove an error or avoidable rework. Findings show thresholds, comparison cohorts, affected cases, original-row evidence and caveats. Frequency alone is not evidence of a bottleneck.
- Variant sequences use the backend's canonical ordering. Incomplete, cancelled and unknown-status cases remain observed traces according to the selected discovery configuration. Completion is not inferred from an activity name; completion rates are shown only where supported.
- Timelines display UTC and preserve original attributes. `source_row` counts data records from 1 after the CSV header; it is not necessarily a physical line number. Original event-order information is retained for consistent ties.

See [discovery](discovery.md) and [analytics](analytics.md) for complete algorithms, metrics, status interpretation and threshold definitions.

## Paginated inspection APIs

Paths in this table are relative to `/api/v1/datasets/{id}`. `offset` is nonnegative and `limit` is 1–200. List responses include `analysis_id`, `total`, `offset`, `limit` and `items`.

| Path | Filters and returned data |
| --- | --- |
| `/analytics/findings` | `process_id`, `category`, `severity`, `entity_id`; measured finding, threshold/baseline, affected cases, evidence and limitations |
| `/analytics/processes/{process_id}/variants` | Variant sequences, counts, case share and duration distributions |
| `/recommendations` | `process_id`; finding-linked actions, evidence summary, measurement plan, caveats, priority and affected-case count |
| `/cases` | `process_id`, `variant_id`, `search`; case ID, process, variant, event count, observed duration and status |
| `/cases/{case_token}` | Paginated ordered canonical events plus case summary and `total_events`; default limit 100 |

Case `search` is a case-insensitive substring match on the raw source case ID. Use the case list's opaque `id` in the detail URL; `case_id` remains the original display value. This keeps identical source case IDs in separate processes distinct. Case responses reference the discovery analysis ID; recommendations reference the analytics analysis ID.

Recommendations are deterministic review actions selected from actual finding categories. Each includes `finding_ids`, `evidence_summary`, `actions`, `measurement_plan`, `caveats` and `affected_case_count`. They ask the analyst to investigate and validate potential changes; they do not claim a root cause or forecast savings. `expected_improvement` is always null. No qualifying findings means no recommendations.

## Local verification

Run the frontend type checks, tests and build plus the backend test suite documented in the [README](../../README.md). With both local servers running, explicitly upload the existing development CSV and confirm its mappings. Verify all stages complete, the five main areas show actual results, node/edge inspection and filters work, variant links open matching cases, and timeline pages preserve source evidence. Refresh an explicit dataset URL, then open a fresh URL without a dataset parameter to verify the empty state. Exercise failed validation and unavailable-backend states, and inspect narrow-screen navigation and panels.

The synthetic fixture stays outside production source and is never loaded automatically. Authentication, multi-user authorization, durable queues, distributed locks and production deployment remain separate work.
