# 9 Testing and Evaluation

## Evaluation purpose and evidence boundaries

The evaluation asks whether the software transforms supplied event logs into consistent, inspectable process results. It does not establish that a particular university has the simulated delays, workload patterns or rework. The primary research fixture is synthetic; the university's lack of suitable operational HR logs is the project context supplied by the researcher, not a conclusion established through this software evaluation.

The refined fixture contains 4,700 events, 500 cases and four process types. It simulates Recruitment, Employee Onboarding, Leave Management and Monthly Payroll; its literal process labels are `Recruitment`, `Onboarding`, `Leave Management` and `Payroll`. It represents fictional Wadi Al-Nour University and is not GIU operational data. The original fixture is retained separately. Neither fixture is automatically loaded by the application.

Small controlled logs supplement the HR fixture for edge cases that a realistic combined log may not contain, such as invalid dates, ties, absent process types, overlapping intervals and unfamiliar process names. These are test inputs, not replacement production datasets.

## Test strategy

The backend suite uses pytest and FastAPI TestClient. Validation/normalization tests exercise data semantics directly; discovery tests call real PM4Py and compare results with independently counted sequences; analytics tests compare results with independent arithmetic. API tests verify the request/response contract, error handling, persistence, cache invalidation and lifecycle restrictions. Workspace tests exercise actual background jobs, recommendations and case APIs.

Frontend Vitest tests cover API transport and error handling, analysis contract decoding, cancellation, formatting, upload-wizard state and case-completion mapping. They use isolated inputs and mocked transport where appropriate; they are not substitutes for browser-to-backend integration tests. Browser scripts recorded separately exercise real APIs, rendered data, navigation, dialog interactions and responsive layouts.

Independent fixture auditing compares the uploaded application's results with CSV-derived counts, sequences and timestamp calculations. It checks internal consistency and provenance. This approach cannot establish whether the synthetic distribution represents real HR behavior or whether a recommended intervention would work.

## Checks executed for this documentation

On the 9 November 2026 documentation review, the following commands completed successfully in the existing local environment:

| Check | Observed result | Evidence |
| --- | --- | --- |
| Full backend suite | 135 tests passed; no failures or skips. One Starlette TestClient/httpx deprecation warning was emitted. A separate collection check confirmed 135 collected cases. | [Backend test output](evidence/tests/backend-tests.txt) |
| Refined-fixture discovery and analytics rerun | Four fixture-specific tests passed using `HR_TEST_EVENT_LOG` set to the version 2 CSV; 55 unrelated tests were deselected. One identical dependency warning. These four are reruns under another fixture, not four additional unique suite tests. | [Refined-fixture output](evidence/tests/refined-fixture-tests.txt) |
| Frontend unit tests | 26 tests passed across four files. | [Frontend test output](evidence/tests/frontend-tests.txt) |
| Frontend TypeScript and production build | `tsc -b` and Vite build completed successfully. | [Build output](evidence/tests/frontend-build.txt) |

The backend run used `.venv/Scripts/python.exe -m pytest backend/tests -q` from the repository root. Test collection was checked separately because the repository's quiet-mode configuration suppresses the usual summary line. Fixture-specific checks used:

```powershell
$env:HR_TEST_EVENT_LOG = (Resolve-Path outputs/synthetic_hr_dataset_v2/event_log.csv).Path
& backend/.venv/Scripts/python.exe -m pytest backend/tests/test_discovery.py backend/tests/test_analytics.py -q -o addopts='' -k 'supplied_hr_fixture or discovery_ignores_synthetic or hr_fixture_timings or synthetic_flags'
```

The path in the command above records the location used for this review. In the portable project package, extract the separate dataset archive and replace that path with the actual absolute path to its `event_log.csv`; the project archive does not contain `outputs/`. For example, set `$env:HR_TEST_EVENT_LOG = 'C:\HR-test-data\synthetic_hr_dataset_v2\event_log.csv'` after extracting the fixture there.

The default fixture tests use the separately supplied original CSV when no override is set. They skip fixture-dependent cases if the CSV is absent; no such skips occurred in this review. Unit/API tests create isolated temporary storage rather than replacing the active user dataset.

## Retained integration and browser evidence

The following reports were inspected during documentation preparation. They are retained results of previously executed checks, not new browser runs performed for this documentation. Their boolean checks, completion/result fields and available error arrays were inspected. Counts represent script assertions, not independent users, statistical samples or a coverage percentage.

| Evidence | Recorded result | Scope and interpretation |
| --- | --- | --- |
| [Upload workflow report](evidence/fixture/upload_test_report.json) | 14 checks passed; no recorded browser errors. | A fresh session, real CSV preview and validation, explicit case-status configuration, eight completed stages, observed queued/running/completed states and four discovered processes. |
| [Independent pipeline assessment](evidence/fixture/pipeline_assessment.json) | 4,702 checks passed. | CSV-to-analysis reconciliation, including process/event/case/variant counts, timing and finding evidence; source hash recorded. |
| [Reference dashboard report](evidence/browser/reference-dashboard-report.json) | 139 checks true; no recorded browser errors. | Current compact explorer: API-derived counts/paths, path changes, graph modes, route threshold, timing details, fit control, navigation, empty state and layout widths from 320 to 1,920 pixels. |
| [Executive overview report](evidence/browser/executive-overview-checks.json) | 15 checks true; no recorded browser errors. | Actual KPI totals, priority findings, process drill-down, closure wording, error/retry and responsive layout. |
| [Investigation report](evidence/browser/focused-investigation-report.json) | 36 checks true; no recorded browser errors. | Current bottleneck and recommendation rows, API reconciliation, filters, detail interactions and six widths from 320 to 1,440 pixels. |
| [Path comparison report](evidence/browser/compact-paths-report.json) | 29 checks true; no recorded browser errors. | Four processes' counts, percentages, sequences, case drill-down, pagination and six responsive widths. |
| [Repair checks](evidence/fixture/repair_validation.json), [business consistency audit](evidence/fixture/business_consistency_audit.json), [provenance audit](evidence/fixture/provenance_audit.json) | 25, 91 and 22 checks passed respectively. | Synthetic fixture consistency, recorded changes and preservation of original source evidence. These are data audits, not application performance benchmarks. |

Earlier fixture-package browser reports also record 37 frontend-integration, 31 case-view and 25 process-map checks. These predate the latest layout revision and should be treated as historical functional evidence. The current compact-layout reports above provide the more relevant visual-regression evidence. No claim is made that those historical scripts were rerun unchanged against the current layout.

## Executed test cases and unverified evaluation areas

The table groups related assertions into reviewable scenarios. A row marked Passed is supported by executed test functions or a recorded report; it is not a claim that every possible input in that feature has been tested.

| Test ID | Feature | Scenario | Input | Expected result | Actual result | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T-001 | API foundation | Health, safe errors and empty startup | Health/error requests; no selected dataset | Contract response; safe errors; no sample ingestion | Backend foundation tests passed | Passed, rerun |
| T-002 | Ingestion and storage | Preview, malformed files, limits, restart and source tampering | Valid and invalid CSVs; modified stored source | Correct preview; bounded/rejected inputs; persistence; stale-source refusal | Ingestion API tests passed | Passed, rerun |
| T-003 | Mapping and validation | Required fields, renamed columns, invalid timestamps and optional omissions | Controlled valid/invalid logs | Blocking errors where required; optional gaps nonblocking | Validation/normalization tests passed | Passed, rerun |
| T-004 | Ordering and time | Tied events, explicit order, DST ambiguity, duplicates and invalid intervals | Controlled timestamps and event IDs | Deterministic UTC ordering; clear issues; no silent deletion | Validation and ordering assertions passed | Passed, rerun |
| T-005 | Discovery and variants | Branches, loops, single/unknown processes, status handling and optional induction | Controlled sequences and status mappings | Exact DFG/variants; independent process groups; explicit induction policy | Real PM4Py discovery tests passed | Passed, rerun |
| T-006 | Analytics and findings | Exact durations, approximations, overlaps, thresholds and resource coverage | Controlled processing/waiting intervals | Independent arithmetic agrees; unsupported measurements absent | Analytics tests passed | Passed, rerun |
| T-007 | Workspace pipeline | Actual stages, polling, restart, recommendations and case timelines | Validated logs and background jobs | Observable stages; correct failure state; linked evidence and events | Workspace tests passed | Passed, rerun |
| T-008 | HR fixture reconciliation | Counts, sequences, timings and independence from synthetic flags | Original and refined 4,700-event logs | Four separate processes; results agree with source calculations | Full suite plus four refined-fixture checks passed | Passed, rerun |
| T-009 | Browser upload | Upload through completed real analysis | Refined CSV and explicit status mapping | Preview to four ready process models, without fake progress | 14 recorded browser checks passed | Passed, recorded |
| T-010 | Explorer and overview | Render API-derived data and preserve navigation context | Saved refined analysis | Correct counts/paths; usable navigation and empty/error states | 139 explorer/reference and 15 overview checks passed | Passed, recorded |
| T-011 | Findings and recommendations | Filter and inspect real evidence/action details | Saved refined analysis | Visible rows/details match backend results | 36 recorded checks passed | Passed, recorded |
| T-012 | Frontend logic | Transport errors, wizard state, job decoding and status mapping | Isolated test inputs/mock transport | Valid transitions and safe errors; unavailable remains distinct from zero | 26 tests across four files passed | Passed, rerun |
| T-013 | Build | Type checking and production bundling | Current frontend source | No TypeScript or build failure | TypeScript and Vite completed successfully | Passed, rerun |
| T-014 | Paths and case drill-down | Inspect sequences and navigate to matching cases | Four processes' backend variants | Correct sequence, count, share and variant filter | 29 current-path browser checks; backend case-sequence assertions passed | Passed, mixed evidence |
| T-015 | Data provenance | Reconcile source identity and documented fixture changes | Original/refined CSVs and audit files | Source preserved; changes and relationships traceable | Retained 25/91/22-check audits passed | Passed, recorded |
| T-016 | Independent full-pipeline oracle | Compare source CSV with uploaded analysis without importing mining engine | Refined CSV and saved real API results | Counts, sequences, timestamps and finding samples agree | 4,702 recorded comparisons passed | Passed, recorded |
| T-017 | Operational validity | Evaluate real university HR event logs | Anonymized real operational logs | Agreement with verified business records and expert interpretation | Suitable real logs have not been evaluated | Not Tested |
| T-018 | Capacity | Maximum-size and concurrent-user performance | Controlled load at defined deployment sizes | Measurements against an agreed target | No load benchmark or service-level target established | Not Tested |
| T-019 | Security | Penetration and privacy assessment | Deployed service and real-data governance model | Risks assessed and controls independently verified | No such assessment performed | Not Tested |
| T-020 | Human factors | Formal accessibility and representative-user evaluation | Assistive technology and target participants | Documented accessibility/usability findings | No formal audit or user study performed | Not Tested |

## Test implementation traceability

| Test groups | Implemented test sources |
| --- | --- |
| T-001 | [test_foundation.py](../backend/tests/test_foundation.py) |
| T-002 | [test_ingestion_api.py](../backend/tests/test_ingestion_api.py) |
| T-003 and T-004 | [test_validation_normalization.py](../backend/tests/test_validation_normalization.py) |
| T-005 and discovery part of T-008 | [test_discovery.py](../backend/tests/test_discovery.py), including `test_supplied_hr_fixture_counts_sequences_and_four_independent_models` and `test_discovery_ignores_synthetic_delay_rework_exception_flags` |
| T-006 and analytics part of T-008 | [test_analytics.py](../backend/tests/test_analytics.py), including `test_hr_fixture_timings_counts_and_resources_match_independent_calculations` and `test_synthetic_flags_and_precomputed_duration_columns_do_not_drive_analytics` |
| T-007 and case part of T-014 | [test_workspace.py](../backend/tests/test_workspace.py) |
| T-010, T-011 and browser part of T-014 | [Explorer/reference script](evidence/browser/verify_dashboard_reference.mjs), [overview script](evidence/browser/inspect_executive_overview.mjs), [investigation script](evidence/browser/verify_focused_investigation.mjs), [paths script](evidence/browser/verify_compact_paths.mjs) |
| T-012 | [API transport tests](../frontend/src/lib/api/client.test.ts), [analysis contract tests](../frontend/src/lib/api/analysis.test.ts), [wizard tests](../frontend/src/features/datasets/wizardState.test.ts), [case-completion tests](../frontend/src/features/datasets/caseCompletion.test.ts) |
| T-016 | [Independent pipeline verifier](evidence/fixture/verify_refined_pipeline.py) |

## Synthetic evaluation results and interpretation

The retained refined-fixture assessment reports 500 cases, 4,700 events and 51 variants across four independent processes. With explicit case-status mapping, 483 cases are closed, 12 incomplete and five cancelled. The closed group includes 14 rejected outcomes; closure does not imply a favorable outcome. Without that explicit interpretation, the application must not assume those case states from event status.

Recorded validation has zero blocking errors, zero warnings and one informational observation for unmapped optional cost. There are 4,200 adjacent-event pairs with interval measurements in this fixture; the recorded assessment has zero approximate pairs and zero overlaps. Controlled unit tests, rather than this particular fixture, therefore supply evidence for approximation and overlap behavior.

The retained analysis contains 62 findings and 62 linked recommendations. Its independent assessment checks 442 cited evidence samples across six finding categories. These counts demonstrate that the rules and evidence pipeline run on simulated events. They are not a measurement of the university's actual bottlenecks, proof that a delay is avoidable, or evidence that a suggested change yields savings. Calendar gaps include non-working periods and legitimate scheduled waiting; the application does not automatically apply the supplementary business calendar to its elapsed-time analytics.

The most important next evaluation is a governed study using anonymized real HR event logs, independently verified event meanings and case closure, business-owner review of findings, and documented before/after measurements for any intervention. Test success on synthetic data establishes technical consistency within the tested inputs, not external operational validity.
