# 5 Data model and event log structure

## 5.1 Event logs and case identity

An event log records observed activities performed in individual process instances. A case is one instance, such as one leave request; an event is one recorded activity in that instance. The application accepts a CSV containing one event per row. The user maps source columns to canonical fields before analysis. The system does not require a fixed HR vocabulary, predefined activity sequence, or particular synthetic dataset.

The logical case identity is the pair `(process_type, case_id)`. An identical case ID in two process types therefore identifies two separate cases. The internal `case_key` is a JSON encoding of that pair, avoiding collisions caused by simple string concatenation. Process labels are grouped exactly after surrounding whitespace is removed; they are not automatically merged by spelling or case similarity. Without a mapped process field, every event receives `Single process`.

This is an observed-data model. An expected process model specifies how work should be performed. The discovered DFG and process tree describe patterns in the supplied events; they are not an approved HR policy. Expected-model import, conformance replay, fitness evaluation against a prescribed workflow, and policy-compliance certification are not implemented.

## 5.2 Canonical data dictionary

Examples below illustrate field formats; they are not real university records. Nullable optional values are retained as null when unavailable. Canonical text values are trimmed, while original CSV cells are preserved in `attributes`.

| Field | Canonical type | Requirement | Meaning and example |
| --- | --- | --- | --- |
| `case_id` | String | Required | Nonempty process-instance identifier; `REQ-001`. Leading zeros are preserved. |
| `activity` | String | Required | Nonempty activity name; `Review request`. |
| `timestamp` | UTC ISO 8601 string | Required | Ordering instant; completion timestamp is recommended. Example: `2025-02-03T08:30:00+00:00`. |
| `process_type` | String | Optional mapping | Explicit workflow separation label; `Leave Management`. If mapped, empty cells block validation. If unmapped, `Single process`. |
| `event_id` | String or null | Optional | Source event identifier; `EV-001`. Conflicting contents under the same ID anywhere in the uploaded dataset block processing. |
| `resource_id` | String or null | Optional | Performer identifier; `RES-012`. Used for assignment analysis when available. |
| `resource_name` | String or null | Optional | Performer display name; `Example Analyst`. Also available as an assignment identifier fallback when resource IDs are unavailable. |
| `resource_role` | String or null | Optional | Role attached to the event; `HR specialist`. It supplies descriptive context, not an authorization rule. |
| `department` | String or null | Optional | Event department label or identifier; `Human Resources`. Its business meaning must be consistent in the uploaded log. |
| `activity_start` | UTC ISO 8601 string or null | Optional | Activity start instant; `2025-02-03T08:00:00+00:00`. |
| `activity_end` | UTC ISO 8601 string or null | Optional | Activity end instant; `2025-02-03T08:30:00+00:00`. May share the same source column as `timestamp`. |
| `cost` | Finite number or null | Optional | Source event cost; `125.5`. Invalid numeric text produces a warning and canonical null. Currency and cost aggregation are not implemented. |
| `outcome` | String or null | Optional | Event outcome, retained for inspection; `Approved`. This is not automatically a case-completion label. |
| `status` | String or null | Optional | Event-level status; `Completed`. It is not automatically interpreted as whole-case status. |
| `event_order` | Positive integer | Optional input; generated output | Source order can break equal-timestamp ties. Normalization regenerates a contiguous sequence beginning at 1 within each case. |
| `source_event_order` | Positive integer or null | Generated | Original mapped order preserved separately; `3`. |
| `source_row` | Positive integer | Generated | One-based CSV data-record index, excluding the header; `27`. It is not a physical line number when quoted cells contain newlines. |
| `case_key` | String | Generated | Collision-safe process/case identity; `["Leave Management","REQ-001"]`. |
| `attributes` | JSON object | Generated | All original source columns and values, including unmapped fields, retained for traceability and case inspection. |

Cost validation accepts finite numbers, including negative values; it does not impose a currency, sign convention, or accounting policy. Input `event_order` must fit a positive signed 64-bit integer. Custom fields are preserved in `attributes`; adding arbitrary names to the canonical `mapping` dictionary is rejected.

## 5.3 Source preservation and ordering

CSV ingestion reads cells as strings with automatic NA conversion disabled. Literal identifiers such as `NA` and `00042` are therefore preserved. The original uploaded bytes remain in `source.csv`. Preview statistics count missing cells and unique nonempty values across the file; displayed records are limited to the configured preview size, at most 20. Type suggestions use up to 500 nonempty samples per column and are hints, not coercion rules.

The normalizer converts supported timestamp fields to UTC. Offset-aware timestamps retain their instant. Naive timestamps are localized using the explicitly selected IANA timezone, defaulting to UTC. Ambiguous or nonexistent local times at daylight-saving transitions are blocking errors rather than silently inferred. A timestamp format and day-first option can be supplied. Ambiguous day/month text without an explicit format produces a warning.

Events are sorted by process type, case ID, timestamp, source event order for equal-time records, and source row. Missing source-order values sort after present values at the same instant. Original order remains inspectable; canonical order is generated after sorting. Timestamp precedence can differ from the supplied source sequence, and the validator reports such conflicts. Duplicate records are reported and retained; no silent deduplication occurs.

Supplied activity intervals must not run backwards, and the event timestamp must lie inside the available interval bounds. A timestamp inside the interval but different from its end produces a warning. Missing optional columns are informational; missing values in mapped optional columns are warnings. Invalid supplied optional timestamps are errors because they would corrupt time measurements.

## 5.4 Explicit case completion configuration

Case completion is configured separately from column mapping through `DiscoveryRequest.case_status_attribute` and `case_status_values`. The attribute name identifies an original CSV column retained in each event's `attributes`. Its literal values are mapped by the user to `completed`, `incomplete`, `cancelled`, or `unknown`. Matching trims whitespace and ignores case; duplicate keys under that normalization are rejected. Both the attribute and value mapping must be supplied together.

Without this configuration, case status is `unknown`. A case containing conflicting mapped states or unrecognized values is flagged in discovery metadata; conflicting states resolve to `unknown`. The system does not infer completion solely from the last activity or event status. Interpreting a rejected request as `completed` means the case is closed, not that its business outcome was successful. Completion metrics report the coverage of known statuses and separate rates over all cases and over known-status cases. The overall rate is null if any case status is unknown; the known-status rate is null when no statuses are known.

## 5.5 Analysis entities and identifiers

| Entity | Identity and relationship | Principal content |
| --- | --- | --- |
| Dataset | Server-generated UUID | Filename, preview, source hash, validation revision, normalized hash, preparation status. |
| Validation revision | UUID associated with a dataset | Mapping settings, validation report and source fingerprint. Processing must use the current revision. |
| Analysis job | UUID associated with a dataset | Real execution-stage states, timestamps, errors and generated analysis IDs. |
| Discovery result | Analysis UUID bound to validation and normalized hash | Process models, PM4Py version and configuration. Variants are served through paginated routes. |
| Process and activity | Stable prefixed hash identifiers | Observed labels, counts, boundaries, transitions and model metadata. |
| Transition | Stable identifier derived from its process and endpoints | Frequency, participating cases, elapsed and interval gaps, loop indicators. |
| Variant | Stable identifier derived from process and exact activity sequence | Sequence, case count, case share, observed durations and status distribution. |
| Analytics result | Analysis UUID referencing discovery analysis UUID | Process, activity, transition and assignment metrics; separate findings and variant pages. |
| Finding | Evidence-bearing analysis entity | Category, measured value, baseline, affected cases, severity, source-row examples and caveats. |
| Recommendation | Entity linked to finding IDs | Proposed investigation/actions and measurement plan; no promised improvement value. |
| Case view | Stable case token derived from process and source case ID | Summary and paginated normalized event timeline with original attributes. |

Stable process, activity, transition, variant and case tokens use SHA-256-derived identifiers with a kind prefix and a 24-hex-character digest suffix. They are not UUIDs. Source labels and sequences, rather than display order, determine their identity. The `case_id` route parameter for case detail is this stable case token; it is not the source business identifier displayed in the table.

## 5.6 Persistence and supplementary data

Each dataset has a UUID-named directory in the configured local storage root, by default `backend/runtime/datasets`. Files include `source.csv`, `metadata.json`, `validation.json`, `normalized.jsonl`, `result.json`, `discovery.json`, `analytics.json`, `recommendations.json`, and job-status JSON files. JSON writes use temporary files and atomic replacement; source and normalized hashes and revision checks prevent stale results from being silently reused. This is filesystem persistence, not a relational database or a managed historical-analysis catalogue.

The development fixture includes a main event log and supplementary case, resource, department, employee, candidate, and business-calendar CSVs. These describe simulated operations at the fictional Wadi Al-Nour University. The refined event log was enriched offline with relevant context for testing. The application itself uploads one event-log CSV at a time: it does not automatically join supplementary files, query an HR system, or apply the business calendar to duration calculations. Optional context must already be present in the uploaded event rows to be inspected or analyzed.

All development results are technical findings about simulated records. They do not establish the actual operational performance of GIU or another university. A future evaluation with anonymized real HR logs should validate case definitions, source timestamps, process labels and completion semantics before interpreting results operationally.

## 5.7 Implementation traceability

Authoritative sources: [canonical mappings](../backend/app/services/mapping/mapper.py), [CSV reader](../backend/app/services/ingestion/csv_reader.py), [validation engine](../backend/app/services/validation/engine.py), [normalizer](../backend/app/services/normalization/normalizer.py), [process separation](../backend/app/services/process_separation/separator.py), [discovery log and stable IDs](../backend/app/services/discovery/log.py), [dataset contracts](../backend/app/schemas/datasets.py), [discovery contracts](../backend/app/schemas/discovery.py), [analytics contracts](../backend/app/schemas/analytics.py), [case and job contracts](../backend/app/schemas/workspace.py), and [dataset storage](../backend/app/services/ingestion/storage.py).
