# 2 System Requirements

This specification describes the inspected implementation, rather than a proposed enterprise product. Priorities indicate importance to the research workflow; they are documentation classifications, not evidence of stakeholder sign-off. **Implemented** means that the stated bounded capability exists. **Partially Implemented** identifies a concrete capability with missing elements. **Planned** denotes an enhancement, not available behavior. Functional acceptance evidence is summarized in [Testing and evaluation](09-testing-and-evaluation.md).

## Functional requirements

### FR-001 CSV event-log upload

- **Requirement:** Accept a user-selected CSV event log.
- **Description:** Provide file browsing and drag and drop, with client checks and authoritative backend validation of the upload. A fresh session does not load a sample automatically.
- **Priority:** High.
- **Input:** One CSV file within configured file, row and column limits.
- **Expected Output:** A stored dataset identifier and preview, or an actionable structured error.
- **Acceptance Criteria:** Valid input is accepted; unsupported, malformed, empty and oversized input is rejected; filenames cannot choose storage paths.
- **Status:** Implemented.
- **Traceability:** [UploadPage](../frontend/src/features/datasets/UploadPage.tsx), [CSV reader](../backend/app/services/ingestion/csv_reader.py); tests T-001 and T-002.

### FR-002 Dataset preview

- **Requirement:** Show an informative, bounded preview before analysis.
- **Description:** Present the filename, row and column totals, detected columns, inferred types, missing-value counts, sample rows and basic statistics without rendering the entire CSV.
- **Priority:** High.
- **Input:** Successfully uploaded CSV.
- **Expected Output:** Dataset metadata and up to the configured number of preview records.
- **Acceptance Criteria:** Totals and column statistics match source data; leading-zero identifiers remain strings; preview rows respect the configured cap.
- **Status:** Implemented.
- **Traceability:** [PreviewTable](../frontend/src/features/datasets/PreviewTable.tsx), [CSV reader](../backend/app/services/ingestion/csv_reader.py); test T-002.

### FR-003 Configurable column mapping

- **Requirement:** Map source columns to canonical event attributes.
- **Description:** Suggest recognizable names while permitting manual changes, arbitrary process labels, timezone settings, date-order settings and an optional explicit timestamp format.
- **Priority:** High.
- **Input:** Source column names and the analyst's mapping selections.
- **Expected Output:** A mapping for case ID, activity and timestamp, with supported optional fields.
- **Acceptance Criteria:** Renamed columns work through manual mapping; unknown mapped columns or absent required mappings block confirmation.
- **Status:** Implemented.
- **Traceability:** [Mapper](../backend/app/services/mapping/mapper.py), [wizard state](../frontend/src/features/datasets/wizardState.ts); tests T-003 and T-012.

### FR-004 Event-log validation

- **Requirement:** Distinguish blocking errors, warnings and informational observations.
- **Description:** Check empty required values, invalid timestamps, duplicate events, conflicting event identifiers, order inconsistencies, singleton cases and invalid intervals. Missing optional attributes alone must not reject the log.
- **Priority:** High.
- **Input:** Uploaded source data and mapping/time interpretation.
- **Expected Output:** An issue report with counts, examples and resolution guidance.
- **Acceptance Criteria:** Invalid records are reported without silent deletion; blocking errors prevent processing; warnings require acknowledgment; mapping changes invalidate prior confirmation.
- **Status:** Implemented.
- **Traceability:** [Validation engine](../backend/app/services/validation/engine.py), [ValidationIssues](../frontend/src/features/datasets/ValidationIssues.tsx); tests T-003 and T-004.

### FR-005 Normalization and provenance

- **Requirement:** Produce a consistent event log while preserving source information.
- **Description:** Normalize timestamp instants to UTC and order each case by timestamp, explicit event order when supplied, then source row. Retain original attributes and source-row references.
- **Priority:** High.
- **Input:** Validated mapped source records.
- **Expected Output:** Persisted canonical events, collision-safe case keys and a normalized preview.
- **Acceptance Criteria:** Offset-aware dates preserve their instants; ambiguous or nonexistent local times are handled explicitly; ties have deterministic ordering; duplicates remain observable after warning.
- **Status:** Implemented.
- **Traceability:** [Normalizer](../backend/app/services/normalization/normalizer.py), [validation tests](../backend/tests/test_validation_normalization.py); tests T-003 and T-004.

### FR-006 Process separation

- **Requirement:** Mine unrelated process types independently.
- **Description:** Use an explicitly mapped process-type field; without one, treat the log as a single process. Names are data-driven, not a fixed HR taxonomy.
- **Priority:** High.
- **Input:** Normalized events with or without process type.
- **Expected Output:** Independent process groups and case namespaces.
- **Acceptance Criteria:** Reused case IDs in different process types do not merge; an unfamiliar process and a log without process type both work; the supplied combined fixture yields four groups.
- **Status:** Implemented.
- **Traceability:** [Separator](../backend/app/services/process_separation/separator.py), [discovery log preparation](../backend/app/services/discovery/log.py); tests T-005 and T-008.

### FR-007 Data-driven process discovery

- **Requirement:** Discover models from observed event sequences in the backend.
- **Description:** Produce an exact observed DFG, starts, ends, frequencies and repetitions; perform optional eligible Inductive Miner discovery and serialize its process tree/Petri net into JSON.
- **Priority:** High.
- **Input:** Confirmed normalized log and discovery options.
- **Expected Output:** Process models, stable activity/transition identifiers and discovery metadata, including skipped or failed optional induction.
- **Acceptance Criteria:** Frequencies match independent sequence counts; single-case and oversized induction policies are explicit; changing synthetic flags does not alter discovery.
- **Status:** Implemented.
- **Traceability:** [Discovery engine](../backend/app/services/discovery/engine.py), [serialization](../backend/app/services/discovery/serialization.py); tests T-005 and T-008.

### FR-008 Interactive process exploration

- **Requirement:** Render actual discovered paths and measurements interactively.
- **Description:** Provide frequency, time and rework modes, process selection, selected-path/all-path views, zoom, pan, fit, route filtering and node/edge detail dialogs. The task-style display is not a BPMN conformance model.
- **Priority:** High.
- **Input:** Backend process models, variants and analytics.
- **Expected Output:** A React Flow diagram and contextual metrics with approximation labels where necessary.
- **Acceptance Criteria:** Rendered activities, transitions and path sequences reconcile with API data; selecting a path changes the map; metric scope remains clearly identified.
- **Status:** Implemented.
- **Traceability:** [ProcessExplorerPage](../frontend/src/features/process-explorer/ProcessExplorerPage.tsx), [ProcessMap](../frontend/src/features/process-explorer/ProcessMap.tsx); tests T-010 and T-014.

### FR-009 Performance analytics

- **Requirement:** Calculate process, activity, transition, variant and supported resource statistics.
- **Description:** Calculate case/event totals, observed case-duration distributions, interval-based processing time, measured waiting gaps and separately labeled timestamp approximations. Include resource/department observations only where supported.
- **Priority:** High.
- **Input:** Normalized events and discovery results.
- **Expected Output:** Structured metrics with sample coverage, unavailable values and measurement semantics.
- **Acceptance Criteria:** Independent arithmetic matches counts and durations; absent intervals do not become exact processing time; overlaps do not become negative waiting time; process baselines remain independent.
- **Status:** Implemented.
- **Traceability:** [Analytics engine](../backend/app/services/analytics/engine.py), [measurements](../backend/app/services/analytics/measurements.py), [resources](../backend/app/services/analytics/resources.py); tests T-006 and T-008.

### FR-010 Evidence-based bottleneck findings

- **Requirement:** Identify unusual durations, repetition, handovers and workload concentration with evidence.
- **Description:** Apply process-specific statistical comparisons or configured business thresholds; expose observed values, baselines, affected cases, severity and source examples. Frequency alone is not sufficient proof of a bottleneck.
- **Priority:** High.
- **Input:** Supported measurements, sequences and optional threshold configuration.
- **Expected Output:** Filterable findings by process, severity, category and activity/transition.
- **Acceptance Criteria:** Each finding links to measured observations and its comparison; unsupported capacity or causal claims are absent; missing resource information does not generate invented resource findings.
- **Status:** Implemented.
- **Traceability:** [Bottleneck engine](../backend/app/services/bottlenecks/engine.py), [BottlenecksPage](../frontend/src/features/bottlenecks/BottlenecksPage.tsx); tests T-006, T-008 and T-011.

### FR-011 Variant comparison

- **Requirement:** Group cases by their exact ordered activity sequence.
- **Description:** Expose path identifiers, sequence, case count, percentage, duration statistics and repetition observations. Preserve incomplete and cancelled traces as observed variants.
- **Priority:** High.
- **Input:** Chronologically ordered cases within each process.
- **Expected Output:** Ranked, paginated variant comparisons and sequence detail with case drill-down.
- **Acceptance Criteria:** Case counts reconcile with independent sequence grouping; percentages sum to the process total within numerical tolerance; selecting a variant filters its cases.
- **Status:** Implemented.
- **Traceability:** [Variant engine](../backend/app/services/variants/engine.py), [VariantsPage](../frontend/src/features/variants/VariantsPage.tsx); tests T-005 and T-014.

### FR-012 Case exploration

- **Requirement:** Inspect the execution history of a selected case.
- **Description:** Search and filter cases, then open a dialog containing chronological events, timestamps and available resource, department and original attributes. Backend pagination bounds case and event responses.
- **Priority:** High.
- **Input:** Dataset, optional process/variant/search filters and a case token.
- **Expected Output:** Case summaries and a selected case timeline.
- **Acceptance Criteria:** Timeline order matches the corresponding variant; source attributes remain available; process and variant filters are honored.
- **Status:** Implemented.
- **Traceability:** [Workspace service](../backend/app/services/orchestration/workspace.py), [CaseExplorerPage](../frontend/src/features/cases/CaseExplorerPage.tsx); tests T-007 and T-014.

### FR-013 Recommendation review

- **Requirement:** Generate investigation actions linked to observed findings.
- **Description:** Use explicit category rules to suggest evidence review, cautious intervention and follow-up measurements. Recommendations do not establish a root cause or predict numerical savings.
- **Priority:** High.
- **Input:** Valid bottleneck findings and associated evidence.
- **Expected Output:** Prioritized, filterable recommendations with linked findings and review dialogs.
- **Acceptance Criteria:** Every recommendation references an existing finding; unsupported projected improvements remain null; displayed actions match backend responses.
- **Status:** Implemented.
- **Traceability:** [Recommendation engine](../backend/app/services/recommendations/engine.py), [RecommendationsPage](../frontend/src/features/recommendations/RecommendationsPage.tsx); tests T-007 and T-011.

### FR-014 Observable analysis orchestration

- **Requirement:** Run and report the real analysis pipeline after confirmation.
- **Description:** Expose queued, running, completed and failed jobs with eight actual processing stages. Repeated starts for the same active dataset reuse its job; the local queue is bounded.
- **Priority:** High.
- **Input:** Latest validation identifier, acknowledgment where required and optional analytics settings.
- **Expected Output:** Pollable job state and completed analysis artifacts, or an actionable failure.
- **Acceptance Criteria:** Unrun stages do not become complete after failure; stage callbacks reflect actual work; status polling remains responsive during computation; restart reports interrupted work as failed.
- **Status:** Implemented.
- **Traceability:** [Job orchestration](../backend/app/services/orchestration/jobs.py), [AnalysisGate](../frontend/src/features/analysis/AnalysisGate.tsx); tests T-007 and T-009.

### FR-015 Dataset and analysis lifecycle

- **Requirement:** Persist confirmed data and analyses and manage the active workspace selection.
- **Description:** Store source and analysis files locally, reject stale or modified inputs, support reopening an explicit dataset URL and allow another upload or closing the current selection. Closing is not deletion.
- **Priority:** High.
- **Input:** Dataset identifier, validated revisions and user navigation.
- **Expected Output:** Reusable saved results and an explicit active-dataset state.
- **Acceptance Criteria:** Saved results survive application recreation; remapping invalidates dependent artifacts; fresh navigation without a dataset starts empty. Dataset catalog browsing, deletion, retention and historical comparison remain unavailable.
- **Status:** Partially Implemented, because lifecycle management is limited to local persistence and explicit selection.
- **Traceability:** [Dataset store](../backend/app/services/ingestion/storage.py), [DatasetContext](../frontend/src/features/datasets/DatasetContext.tsx), [AnalysisContext](../frontend/src/features/analysis/AnalysisContext.tsx); tests T-002, T-007 and T-010.

### FR-016 Explicit case-completion interpretation

- **Requirement:** Interpret case closure only from analyst-configured case-level evidence.
- **Description:** Allow a source attribute and literal values to be mapped to completed, incomplete or cancelled states. Event status alone does not imply case completion; completed means closed, not necessarily successful.
- **Priority:** Medium.
- **Input:** Optional case-status source column and value mapping.
- **Expected Output:** Closure coverage and status-aware case/variant observations; unknown where interpretation is absent or inconsistent.
- **Acceptance Criteria:** Conflicting/unrecognized case states remain unknown; duplicate normalized value rules are rejected; incomplete/cancelled traces remain visible while induction applies its documented eligibility policy.
- **Status:** Implemented.
- **Traceability:** [Case-completion controls](../frontend/src/features/datasets/CaseCompletionSettings.tsx), [case-completion mapping](../frontend/src/features/datasets/caseCompletion.ts), [discovery log preparation](../backend/app/services/discovery/log.py); tests T-005 and T-012.

## Non-functional requirements

| ID and quality attribute | Description and rationale | Verification method | Implementation and verification status |
| --- | --- | --- | --- |
| NFR-001 Performance | Bound uploaded data, previews and result pages, and keep job polling separate from long computation to make local analysis practical. Defaults are 50 MiB, 250,000 rows, 200 columns, 20 preview rows and at most 200 items per paginated API response. These are limits, not demonstrated throughput targets. | Limit-boundary API tests, polling regression and functional fixture runs; dedicated load/latency benchmark would be needed for a service-level claim. | Implemented controls; functional verification passed. Maximum-size performance and latency guarantees Not Tested. |
| NFR-002 Usability | Provide clear empty/loading/error states, explicit upload stages, concise summaries and progressive disclosure so non-specialists can inspect evidence. | Recorded browser navigation, error/retry, detail-dialog and responsive-layout checks; future representative-user study. | Implemented and functionally checked; formal user-study effectiveness Not Tested. |
| NFR-003 Reliability | Preserve committed artifacts, prevent stale analysis, handle duplicate requests and expose interrupted/failed jobs rather than fabricated completion. | Persistence/restart, tampering, revision invalidation, duplicate-start and failed-stage tests. | Implemented local safeguards; regression tests passed. No distributed failover or recovery-time guarantee. |
| NFR-004 Maintainability | Separate schemas, routes and services, use typed frontend contracts and pinned dependencies, and keep validation/discovery/analytics tests independent. | Source inspection, backend regressions, frontend tests and TypeScript/production build. | Implemented modular structure and passing checks; no quantified maintainability score or coverage target is claimed. |
| NFR-005 Scalability | Restrict expensive induction and use bounded pages/queues to avoid unbounded work in a local research deployment. The analysis executor has one worker and permits at most eight active or queued dataset jobs. | Inspect configuration and orchestration; test induction eligibility and queue-related contracts where covered. Multi-user, maximum-size and distributed tests would be required. | Partially Implemented. Local bounds exist; horizontal scaling, distributed locks and production capacity are Not Tested and not implemented. |
| NFR-006 Security and privacy | Validate uploads, isolate UUID storage paths, use explicit browser-origin configuration and return safe error envelopes. Real HR data would additionally require access control and privacy governance. | Existing malformed-input, path-isolation, request-limit, CORS and safe-error tests; separate penetration/privacy assessments needed. | Partially Implemented defensive controls. Authentication, authorization, tenant isolation and encryption management are absent. Penetration testing Not Tested. CORS is not authentication. |
| NFR-007 Compatibility and portability | Use supported declared Python/Node ranges and separate frontend/backend configuration so the project can be installed locally. | Current Windows environment build/tests; clean installations and additional operating systems/browsers require separate runs. | Windows local workflow verified. Cross-platform and comprehensive cross-browser compatibility Not Tested. |
| NFR-008 Accessibility | Provide semantic controls, labels, a skip link, keyboard-operable dialogs/navigation, focus restoration and responsive layouts. | Source inspection and recorded browser interactions; specialist screen-reader and standards audit needed. | Partially verified implementation. No WCAG conformance claim; formal accessibility audit Not Tested. |
| NFR-009 Data integrity | Preserve original strings/attributes, normalize time consistently, namespace cases, retain duplicate observations and verify artifact fingerprints before reuse. | Independent CSV/analysis comparisons, UTC/order tests, hash-tampering tests and source-preservation checks. | Implemented; available automated checks passed. Input truth, omitted real events and business completeness cannot be established by these checks. |

Implementation anchors for these attributes are [configuration](../backend/app/core/config.py), [storage](../backend/app/services/ingestion/storage.py), [upload limits](../backend/app/services/ingestion/limits.py), [job orchestration](../backend/app/services/orchestration/jobs.py), [application layout](../frontend/src/app/AppLayout.tsx), [detail dialog](../frontend/src/components/DetailDialog.tsx) and [API error handling](../frontend/src/lib/api/client.ts).

The status of a requirement does not establish operational validity. All available end-to-end HR evaluations use synthetic data. Real university performance, user acceptance, security assurance and production capacity require separate evidence.
