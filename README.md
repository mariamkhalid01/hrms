# HR Process Mining and Improvement Platform

A React and FastAPI application for analyzing uploaded HR event logs. This release implements **milestone 5: the connected frontend and interactive process visualizations**, using real PM4Py discovery, performance analytics, bottleneck findings and evidence-linked recommendations. Opening the application without an explicit dataset URL starts with an empty workspace. Data enters the application only through an explicit upload.

The [technical documentation](docs/README.md) provides the system requirements, architecture, processing pipeline, data model, API reference, testing evidence and installation guide. Its research findings concern synthetic development data, not the university's actual HR operations.

The five application areas are Overview, Process Explorer, Bottleneck Analysis, Process paths (variants), and Recommendations, with a supporting Case Explorer. The upload workflow is **Upload → Preview → Map Columns → Validate → Confirm → Process**. Confirmation starts a backend job that prepares the data, discovers separate process models, calculates analytics and prepares recommendations. All screens display the resulting backend data. No sample process maps, invented KPIs or default datasets are displayed.

The interface uses full-width pages, readable step diagrams and details on demand. Process Explorer starts with the most common actual case sequence, including its coverage, and offers all recorded paths. Its BPMN-inspired task boxes and observed boundary markers are visual aids rather than a formal BPMN model. Case timelines, finding evidence, path details and recommendation plans open in focused, keyboard-accessible dialogs. Process paths explains variants as cases following the same ordered steps, so analysts can compare common routes, repetitions and observed durations without needing process-mining terminology first.

## Application areas

| Route | Available features |
| --- | --- |
| `/overview` | Actual case/event/process counts, pooled average and median observed case duration, process comparisons and priority findings |
| `/process-explorer` | React Flow maps with Frequency, Performance and Rework modes, process selection, node/edge inspection, zoom, pan and fit-to-screen |
| `/bottlenecks` | Findings filtered by process, severity, category and activity/transition, with thresholds, affected cases and source evidence |
| `/variants` | Actual activity sequences, case frequencies, percentages, duration comparisons and links to matching cases |
| `/recommendations` | Evidence-linked review actions, measurement plans and caveats; causes and expected improvements are not invented |
| `/cases` | Case search and process/variant filtering, paginated event timelines, UTC timestamps, assignments and original attributes |
| `/upload` | Drag-and-drop or browse upload, preview, editable mapping, validation, confirmation and real job stages |

Upload is available throughout the application. Navigation preserves the selected dataset using `?dataset=<dataset UUID>`. Refreshing or opening that explicit URL restores the selection; opening a fresh URL without this parameter selects no previous upload or test fixture. See [the frontend workflow guide](backend/docs/frontend-workflow.md) for the API flow, result semantics and local worker limits.

## Requirements

- Node.js 24 LTS and pnpm 11.25.0.
- Python 3.12, 3.13, or 3.14. Python 3.12 is the baseline development version.
- Two terminal windows: one for each application.

Install pnpm if it is not available:

```text
npm install --global pnpm@11.25.0
```

The frontend lockfile fixes the resolved JavaScript dependency tree. Backend direct dependencies are pinned in `backend/pyproject.toml`, with the tested transitive package versions recorded in `backend/requirements.lock.txt`. Install backend packages in the project virtual environment rather than a shared Python installation.

## Run locally on Windows

Run these commands from the project root in PowerShell. Using the virtual environment's Python directly avoids changing PowerShell's script-execution policy.

Backend terminal:

```powershell
cd backend
py -3.12 -m venv .venv
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd frontend
Copy-Item .env.example .env
pnpm install --frozen-lockfile
pnpm dev
```

Use the copy commands only for first-time setup; keep any existing local configuration when restarting.

## Run locally on macOS or Linux

Backend terminal, from the project root:

```bash
cd backend
python3.12 -m venv .venv
cp .env.example .env
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal, from the project root:

```bash
cd frontend
cp .env.example .env
pnpm install --frozen-lockfile
pnpm dev
```

Open [the application](http://127.0.0.1:5173), [the API health endpoint](http://127.0.0.1:8000/api/v1/health), or [the interactive API documentation](http://127.0.0.1:8000/api/docs). Stop each development server with Ctrl+C in its terminal. The OpenAPI schema is available at `/api/openapi.json`.

## Configuration and communication

The frontend uses a shared typed REST client. `VITE_API_BASE_URL` defaults to `/api/v1`. During development, Vite proxies `/api` to the server configured by `API_PROXY_TARGET`, which defaults to `http://127.0.0.1:8000`. `API_PROXY_TARGET` is a server-side Vite setting; it is not exposed as a browser variable.

The health route is `GET /api/v1/health`. A healthy response contains:

```json
{
  "status": "ok",
  "service": "hr-process-mining-api",
  "version": "0.1.0",
  "environment": "development"
}
```

The application connection indicator reflects this response. A missing backend produces a connection error, not invented analytical results. HTTP errors share an `error` envelope with a machine-readable code, a readable message, and a request identifier where available. The frontend handles network failures, request timeouts, unexpected responses, and API errors centrally.

Each application's `.env.example` documents its settings. Backend variables include `HR_APP_ENV`, `HR_LOG_LEVEL`, `HR_CORS_ORIGINS` (a JSON array), `HR_DATASET_STORAGE_DIR`, `HR_MAX_UPLOAD_BYTES`, `HR_MAX_ROWS`, `HR_MAX_COLUMNS` and `HR_PREVIEW_ROWS`. Upload limits may be lowered from the documented hard caps. Local `.env` files are ignored by Git. Frontend `VITE_` variables become public browser configuration, so never place secrets in them. Backend CORS configuration permits the local frontend origins. If changing ports or using a separately hosted frontend, update both the API base URL/proxy and allowed origins as needed. Restart the corresponding development server after changing environment settings.

Vite's development proxy is not a production reverse proxy. A future deployment should route `/api` to FastAPI and serve the frontend build with an SPA fallback for application routes. Do not expose a development server as a production deployment.

## Project structure and boundaries

```text
frontend/                 React, TypeScript, Vite, and Tailwind application
  src/                    Application shell, routes, components, and API client
  public/                 Original supplied GIU logo and static assets
  .env.example            Browser/API proxy configuration examples
  package.json            Runtime packages and development commands
  pnpm-lock.yaml          Exact resolved frontend dependency graph
backend/
  app/                    FastAPI application, configuration, API, and service boundaries
    api/routes/           Versioned REST endpoints
    core/                 Environment settings, request context, and error handling
    schemas/              Validated JSON response contracts
    services/             Separate modules for the analysis pipeline concerns
  tests/                  Ingestion, normalization, mining and API checks
  scripts/                Explicit live-API verification against an external fixture
  docs/discovery.md       Algorithms, JSON contracts, case policies and limitations
  docs/analytics.md       Metrics, bottleneck rules, thresholds, evidence and API usage
  docs/frontend-workflow.md Connected screens, background jobs, case APIs and local limits
  .env.example            Backend environment and CORS examples
  pyproject.toml          Python package metadata and pinned dependencies
  requirements.lock.txt   Tested transitive Python package versions
outputs/                  Local deliverables and existing synthetic test data; ignored by Git
work/                     Local working and verification artifacts; ignored by Git
```

Process mining runs in the Python backend. React Flow renders interactive process maps and Recharts renders comparisons from API results; neither generates analysis in the browser. Pandas and PM4Py are backend dependencies. Discovery responses use validated JSON models, including React Flow nodes and edges, without exposing raw PM4Py objects.

The backend separates the following responsibilities so later work can be added without coupling algorithms to routes or UI components:

| Responsibility | Boundary |
| --- | --- |
| File ingestion | Receive and inspect uploaded files; no automatic dataset loading |
| Event-log validation | Validate structure and event semantics and report actionable problems |
| Column mapping | Map user-selected columns to the canonical schema |
| Data normalization | Parse timestamps, identifiers, and typed event attributes |
| Process separation | Separate workflows from supplied data, without a fixed HR process list |
| Process discovery | Run PM4Py and produce JSON-ready process representations |
| Performance analytics | Calculate evidence from normalized event records |
| Bottleneck detection | Identify supported timing patterns and their evidence |
| Variant analysis | Compare ordered activity paths and frequencies |
| Recommendations | Produce recommendations tied to measured evidence |
| Orchestration and API | Manage analysis lifecycle and expose stable REST contracts |

Ingestion, mapping, validation, normalization, process separation, discovery, variants, performance analytics, bottleneck screening, recommendations and their orchestration are implemented. Recommendations select review actions from actual finding categories and retain links to the measured evidence. No raw pandas or PM4Py objects are exposed by REST endpoints.

## Data and branding rules

Existing synthetic CSVs are **test data only**. Neither application reads `outputs/`, imports those files at startup, copies their records into source code, nor assumes their process names. They are explicitly supplied to development tests through the upload API. Do not replace or regenerate the supplied test data as part of application development.

The supplied GIU logo is stored at `frontend/public/brand/giu_logo.jpg`. It is a byte-for-byte copy of the supplied JPG, displayed at its original aspect ratio without recoloring or modification.

## Verification commands

From `frontend/`:

```text
pnpm typecheck
pnpm test
pnpm build
```

From `backend/`, using the virtual environment's Python:

```text
python -m pytest
python -m ruff check app tests scripts
```

For Windows without activating the environment, replace `python` above with `.\.venv\Scripts\python.exe`; for macOS/Linux, use `.venv/bin/python`.

With both servers running, the following URLs must return the same healthy service response:

- Direct backend: `http://127.0.0.1:8000/api/v1/health`
- Through the frontend proxy: `http://127.0.0.1:5173/api/v1/health`

Also upload and confirm a dataset, follow the real job stages, visit all five areas and the Case Explorer, inspect a node/edge, change filters, and refresh a nested route with its explicit dataset parameter. Check that a fresh URL without the parameter starts empty. Use **Check backend connection** to verify the unavailable state when the backend is stopped. The indicator reflects the most recent check; it is not continuous uptime monitoring. The milestone progress report records which checks were actually run; these commands are repeatable verification steps.

## Remaining deployment work

Authentication, production deployment, multi-user dataset access controls and a durable distributed worker system remain later work. The connected screens, local background jobs and evidence-based review recommendations are implemented. Current storage and locks assume one backend process; job execution does not survive a server restart and must be retried when interrupted. Recommendations require domain review and do not estimate savings or establish causes.

## Ingestion workflow and data rules

1. Upload a CSV by browsing or dropping a file. Limits are supplied by the backend: by default **50 MiB, 250,000 rows and 200 columns**. Invalid file types, encodings, headers and malformed CSVs produce actionable errors. UTF-8 (including BOM) and BOM-marked UTF-16 are supported.
2. Preview the filename, dimensions, missing-value counts, inferred column types, distinct-value counts and a bounded sample of 20 records. Missing and distinct-value counts cover the whole file; type hints use up to 500 nonempty values per column. The interface never renders the complete file.
3. Review suggested column mappings. Case ID, Activity and Timestamp are required. Process Type, Event ID, resources, department, activity start/end, cost, outcome, status and source event order are optional. All original columns are retained as attributes, including those not mapped.
4. Choose the timezone for timestamps without offsets, optionally select day-first parsing or an explicit timestamp format, then validate. Offset-aware timestamps keep their original instant; canonical times are converted to UTC. Ambiguous or nonexistent daylight-saving local times require correction or explicit source offsets.
5. Resolve blocking errors or go back to change mappings. Warnings require acknowledgment before processing. Missing optional fields do not block the dataset. Issues include explanations, suggested fixes and bounded examples of affected records.
6. Confirm and process. The backend job revalidates the confirmed revision, preserves the original CSV, sorts events within cases, saves canonical records, discovers each process, calculates metrics/findings and prepares recommendations. The interface displays the backend's eight actual stage states, without estimated percentages. The new dataset becomes active only after the job succeeds; a failed replacement leaves the previous active dataset selected. Finalized wizard steps are read-only. Upload the file again to create a fresh mapping without invalidating the selected dataset.

Duplicate records are reported and preserved, not silently removed. Conflicting event identifiers and invalid required values block processing. Source order is retained as `source_row` and `source_event_order`; chronological sorting uses explicit event order for ties and then original row order. Row numbers in validation reports count data records starting at 1 after the header, not physical text-file lines.

When no process field is mapped, the entire dataset is treated as one process. An explicitly mapped process field can be any reliable separation column. Reused case IDs across different processes are namespaced using an unambiguous process/case key and reported rather than merging unrelated cases. No fixed HR process names are built into the ingestion code.

Uploads and normalized records are stored under `backend/runtime/datasets/` by default. `HR_DATASET_STORAGE_DIR` overrides this local directory. Each upload has a server-generated UUID directory, the original `source.csv`, metadata and validation state, and—after processing—canonical `normalized.jsonl` records plus saved analysis and job state. Local files are retained for continued development and are excluded from Git and the source archive. Dataset selection is kept in browser memory and restored only from an explicit `?dataset=<UUID>` URL; there is no last-used dataset or fixture fallback. Closing a dataset clears the selection without deleting its files. Run this development server on localhost and design access control before a multi-user deployment.

## Ingestion REST endpoints

All paths below are relative to `/api/v1`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/datasets/config` | Current upload, row, column and preview limits |
| POST | `/datasets/upload` | Multipart CSV upload and bounded preview |
| GET | `/datasets/{id}` | Uploaded dataset metadata and preview |
| POST | `/datasets/{id}/validate` | Mapping/time settings and structured validation report |
| POST | `/datasets/{id}/process` | Confirm a validation revision and persist normalized records |
| GET | `/datasets/{id}/result` | Prepared dataset summary and dynamic process counts |

Validation returns blocking errors, warnings and informational observations. Each new validation creates a revision. A stale validation ID cannot be used for processing. The process endpoint requires explicit warning acknowledgment when applicable; it does not run mining algorithms or manufacture analysis results.

The frontend uses `POST /datasets/{id}/analysis-jobs` after confirmation to run the complete pipeline, rather than stopping at the preparation-only `/process` endpoint. Poll `GET /datasets/{id}/analysis-jobs/{job_id}` or restore `GET /datasets/{id}/analysis-jobs/latest`. Stages are Reading dataset, Validating event log, Normalizing data, Separating processes, Discovering process models, Calculating performance metrics, Detecting bottlenecks and Preparing recommendations. Completed jobs identify the discovery and analytics results they produced. See [job behavior and recovery](backend/docs/frontend-workflow.md#background-jobs-and-recovery).

Reference: [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/) describes the spooled-upload mechanism used by this backend.

## Process discovery

The frontend's confirmed analysis job runs discovery automatically for the deliberately selected upload. For direct API use after preparing an upload, send its dataset ID to `POST /api/v1/datasets/{id}/discovery` with an empty JSON body `{}`. The default `auto` mode always discovers an exact DFG and exact variants. It also runs Inductive Miner and converts the process tree to a Petri net when the eligible partition is within the configured limits. `algorithm: "dfg"` requests only the observational model; `algorithm: "inductive"` also permits induction from a single multi-event case. The response explains every skipped or failed optional model.

| Method | Path relative to `/api/v1` | Purpose |
| --- | --- | --- |
| POST | `/datasets/{id}/discovery` | Mine the confirmed revision; reuse an identical saved analysis |
| GET | `/datasets/{id}/discovery` | Read current models, provenance and React Flow data |
| GET | `/datasets/{id}/discovery/processes/{process_id}` | Read one process model |
| GET | `/datasets/{id}/discovery/processes/{process_id}/variants?offset=0&limit=50` | Read exact variants, counts, percentages and durations; maximum page size 200 |

Full algorithm choices, case-completion policy, timing definitions, JSON fields, request examples and execution limits are documented in [the discovery guide](backend/docs/discovery.md). The interactive [API documentation](http://127.0.0.1:8000/api/docs) exposes the complete typed schemas.

The development CSV remains outside the application. Tests use the existing `outputs/synthetic_hr_dataset/event_log.csv` when present, or an explicitly configured `HR_TEST_EVENT_LOG` path. The source archive excludes this fixture; set that variable to run the discovery and analytics fixture checks after unpacking. All other backend checks use isolated unit-test records and temporary storage.

With both servers running, repeat live discovery verification from the project root:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_discovery.py --dataset outputs/synthetic_hr_dataset/event_log.csv
```

This explicitly uploads the supplied combined file and two test subsets through Vite's API proxy. It checks real frequencies, sequences and durations against independent calculations and verifies that the original file remains unchanged. Use `--base-url http://127.0.0.1:8000/api/v1` to test the backend directly instead.

## Performance analytics and bottleneck findings

POST `/api/v1/datasets/{id}/analytics` with `{}` after preparing a dataset. This uses the current mined model, creating real discovery if necessary. GET the same path for saved metrics. Find rules, definitions, request examples, limitations and all endpoint details in [the analytics guide](backend/docs/analytics.md).

Metrics include observed case durations, exact activity interval durations, measured gaps and separately labeled waiting-time approximations, variants, completion-status coverage, and resource/department involvement when available. Findings provide their threshold, comparison cohort, affected cases, original-row evidence and limitations. No cause, avoidable cost or improvement is invented.

Use `/analytics/processes/{process_id}` for chart and map inspection data, `/analytics/processes/{process_id}/variants` for paginated variants, and `/analytics/findings` for paginated findings with optional process/category/severity/entity filters. The interactive API documentation has a **Performance and bottlenecks** section.

Repeat the explicit live check using the existing fixture:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_analytics.py --dataset outputs/synthetic_hr_dataset/event_log.csv
```

The local server returns only real calculations. A fresh application URL selects no dataset and runs no analysis. An explicitly selected prepared dataset can start a job if it has no previous job, or refresh stale results; completed matching results are read without rerunning the pipeline.

## Recommendations and case inspection

All paths below are relative to `/api/v1/datasets/{id}`. Each list has bounded `offset`/`limit` pagination, with a maximum page size of 200.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/recommendations?process_id=...&offset=0&limit=50` | Review actions linked to actual finding IDs, evidence summaries, measurement plans and caveats |
| GET | `/cases?process_id=...&variant_id=...&search=...&offset=0&limit=50` | Case summaries filtered by process, variant or case-ID text |
| GET | `/cases/{case_token}?offset=0&limit=100` | Ordered canonical events, original attributes and source-row references for one case |

Case detail uses the opaque `id` returned by the case list, not the raw source `case_id`. Process names and variants come from uploaded records. Recommendations are deterministic review guidance based on supported findings, not proof of an operational cause; `expected_improvement` remains null. The [frontend workflow guide](backend/docs/frontend-workflow.md) documents these contracts and their interpretation.

## Explicit case outcomes and refined development fixture

The upload mapping screen includes **Case completion interpretation (optional)**. Select a source column describing the whole case and assign its values to finished, still open or cancelled groups. No meaning is guessed. Finished means closed, including unsuccessful decisions if you explicitly assign them; it does not imply success. Event Status remains separate. Missing, conflicting and unrecognized outcomes stay unknown.

The separately documented development fixture in `outputs/synthetic_hr_dataset_v2` is uploaded manually. Its `README.md`, assessment, dictionary, methodology and validation report explain the targeted consistency repairs and real application tests. The original release is preserved. Neither fixture is loaded on startup or used as a default dataset.
