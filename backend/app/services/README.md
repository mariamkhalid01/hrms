# Processing boundaries

These packages separate ingestion and future analysis responsibilities. Ingestion,
mapping, validation, normalization, process separation and preparation orchestration are
implemented for milestone 2. Mining modules remain reserved; there are no simulated
results or automatic dataset-loading paths.

| Package | Responsibility |
| --- | --- |
| ingestion | Read explicitly uploaded files and preserve source metadata. |
| validation | Report event-log quality issues before analysis. |
| mapping | Apply analyst-confirmed source-column mappings. |
| normalization | Produce canonical event records and time semantics. |
| process_separation | Group events into processes based on uploaded data. |
| discovery | Execute PM4Py in Python and adapt results to JSON API schemas. |
| analytics | Calculate process, activity and case performance measures. |
| bottlenecks | Detect delays with measurable supporting evidence. |
| variants | Group ordered activity paths and their associated cases. |
| recommendations | Generate improvements tied to analytical findings. |
| orchestration | Coordinate analysis execution, status, results and failures. |

Routes will validate HTTP contracts and delegate work to these modules. Dataframes and
PM4Py objects remain inside the backend; public response schemas belong in `app/schemas`.
Uploads, metadata, validation revisions and canonical JSONL records use local UUID-based
dataset directories under the configured runtime storage path. Preparation is performed
off the async event loop; a durable background mining worker is a later milestone.
