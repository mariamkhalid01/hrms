# Performance analytics and bottleneck screening

Milestone 4 adds real metrics and explainable findings to the existing PM4Py engine. It operates on the same confirmed normalized records, case order, discovered process partitions, activity/transition IDs and exact variants. It never reads synthetic delay/rework/exception flags, precomputed waiting/processing columns, reference tables or fixture files in production.

## API workflow

After uploading, validating and processing a dataset, POST `/api/v1/datasets/{dataset_id}/analytics` with `{}`. This uses the current discovery result, creating real default PM4Py discovery if none exists. To explicitly change discovery settings, include a `discovery` object with the existing discovery request schema. Omitting it preserves the current case-status interpretation. A stale discovery after remapping must be refreshed, either through the discovery endpoint or by explicitly supplying discovery options.

| Method | Path relative to `/api/v1/datasets/{dataset_id}` | Result |
| --- | --- | --- |
| POST | `/analytics` | Calculate metrics/findings, or reuse the same saved analysis |
| GET | `/analytics` | Dataset totals, process metrics, semantics and analysis provenance |
| GET | `/analytics/processes/{process_id}` | One process's metrics, activities, transitions, assignments and finding counts |
| GET | `/analytics/processes/{process_id}/variants?offset=0&limit=50` | Exact variant frequency, duration and repeated-event metrics |
| GET | `/analytics/findings?offset=0&limit=50` | Paginated evidence-based findings |

Findings accept optional `process_id`, `category`, `severity` and `entity_id` filters. `entity_id` connects findings to activity nodes, DFG edges, variants or assignment entries. Pages default to 50 and cap at 200, carry `analysis_id`, and use a stable order. Activity/transition IDs are exactly those returned by discovery, so chart data and process-map inspectors can join them without interpreting labels. Full typed contracts appear in the interactive API documentation under **Performance and bottlenecks**.

## Metric definitions

Each process has its own event/case totals, observed case-duration distribution, processing and waiting distributions, activity and transition metrics, exact variant count, repeated-case count/rate, completion coverage and optional assignment analyses. Dataset totals sum case/event counts; unrelated processes are not pooled into one duration baseline.

Every duration distribution includes sample count, mean, median, minimum and maximum. Count zero has null statistics, not fabricated zero values. All durations use elapsed UTC seconds. Nights, weekends and holidays are included; no business calendar is applied.

| Field | Meaning |
| --- | --- |
| `case_duration_seconds` | Last minus first observed canonical event timestamp; consistent with discovery variants |
| `completed_case_duration_seconds` | The same observed span, restricted to explicitly identified completed cases |
| `full_interval_case_duration_seconds` | Latest activity end minus earliest activity start, only for cases with valid start/end intervals for every event |
| `processing_seconds` | Activity end minus activity start; unavailable when either endpoint is missing |
| `waiting.measured_wait_seconds` | Nonnegative previous activity end → next activity start gaps, where both endpoints exist |
| `waiting.approximate_wait_seconds` | Consecutive canonical timestamp differences when the interval pair is unavailable; these may include processing and unobserved work |
| `waiting.signed_interval_gap_seconds` | All observed interval gaps, including negative overlap values |
| `waiting.overlap_count` | Negative interval gaps, excluded from the nonnegative waiting sample |

Measured gaps show separation between observed intervals, not proven queue time, resource idleness or a cause. Approximate and measured samples are never merged into one waiting mean. Activities expose their incoming waiting metrics separately from processing time. Transition counts and IDs come from the actual discovered DFG. Repeated labels, equal timestamps and acknowledged duplicates retain the original mining semantics.

A single-event case has an observed span of zero, but can still have measured processing time. Summed processing intervals can overlap and are not a decomposition of case duration. Full-interval spans cover observed events only, not work outside the log.

## Completion and resource coverage

Completion uses the explicit case-status mapping already defined by discovery. Event-level Completed statuses do not prove case completion. `completion_rate_percentage` is null if any case has unknown status. A separate `known_status_completion_rate_percentage` divides completed cases by all cases with identified status (completed, incomplete or cancelled), with its denominator and coverage reported. All unknown statuses produce null rates. Observed spans for known incomplete/cancelled cases remain available, but duration findings compare cases only within the same status cohort.

Resource identity uses mapped `resource_id` when available, otherwise mapped `resource_name`. Missing IDs are excluded rather than silently mixed with names. Department identity uses the explicitly mapped department field. Absent resource/department data returns null analyses, not invented members or zero workload. Transition handover fields are null where there is no comparable evidence.

Assignment analyses include known/missing event counts and coverage, event shares among known assignments, distinct case/activity involvement, measured processing distributions/totals and coverage, repeated case assignments, same-activity repeated assignments, and an observed handover matrix. A repeated assignment counts additional events by the same actor/department within a case; it need not mean rework. Handovers compare only immediately adjacent events with both assignments known. They never bridge a missing assignment. Per-case handover comparisons require every assignment in the case to be observed.

Measured work totals are not utilization, available capacity or productivity. They do not adjust for parallel assignments, part-time availability, case complexity or task mix.

## Screening rules and thresholds

Default statistical screening needs at least five observations and at least two affected distinct cases. Quartiles use linear interpolation. A value must strictly exceed:

`max(Q3 + 1.5 × (Q3 − Q1), 2 × median)`

The IQR upper fence follows the [NIST box-plot convention](https://itl.nist.gov/div898/handbook/eda/section3/boxplot.htm). The median multiplier, sample minimum and affected-case minimum are conservative application policies, not statistical significance tests. Zero-IQR cohorts still use the median multiplier. An explicitly configured business threshold replaces the statistical threshold and can operate with fewer observations, while retaining the minimum affected-case requirement.

| Category | Evidence and comparison |
| --- | --- |
| `long_processing` | Activity intervals above that activity's threshold; alternatively, a persistently high activity mean relative to other adequately sampled activity means in the same process |
| `long_waiting` | The same two-stage rule for transitions; measured and approximate samples have entirely separate baselines |
| `repeated_activity` | Percentage of cases containing an activity that repeat it, compared with the configured screening percentage (default 20%) |
| `rework_path` | Extra repeated-label events divided by events in a variant, compared with a configurable screening percentage (default 20%); sufficient case support is required |
| `delayed_cases` | Observed case spans exceeding the same-process, same-status cohort threshold, or an explicit duration threshold |
| `slow_variant` | A supported variant/status cohort's mean span above the corresponding process/status case-duration threshold |
| `frequent_handovers` | Fully observed cases with resource/department change counts above the process-specific baseline or configured limit |
| `workload_imbalance` | Total measured processing time above a robust peer threshold, with full interval coverage; identified single-role resources are compared within their role, unspecified roles separately, and multiple-role resources excluded |

Repetition and handover rules identify review candidates. They do not establish that work is unnecessary. Activity frequency alone never triggers a timing bottleneck. Assignment imbalance findings require measured time, not event count alone. Peer activity/resource comparisons still need human review for different task requirements, capacity or case mix. Sparse or unsupported data can legitimately produce no finding.

Default repeated-work percentages are configurable screening policies, not universal HR benchmarks. Severity prioritizes review by observed-value/threshold ratio: low below 1.25, medium below 2, high at least 2. A zero threshold gives medium priority; approximations are capped at medium. Severity is not a causal confidence score or predicted impact.

Example request, with all duration thresholds in elapsed seconds:

```json
{
  "thresholds": {
    "minimum_samples": 5,
    "minimum_affected_cases": 2,
    "iqr_multiplier": 1.5,
    "minimum_relative_increase": 2,
    "waiting_seconds": 86400,
    "repeated_case_percentage": 25
  },
  "process_overrides": {
    "Your uploaded process name": {
      "case_duration_seconds": 604800,
      "processing_seconds_by_activity": {"Your activity label": 7200}
    }
  }
}
```

Replace example names with names actually present in the uploaded log. Process overrides inherit unspecified global settings. Dictionary overrides replace the corresponding whole dictionary. `waiting_seconds_by_transition` accepts stable transition IDs from discovery; `processing_seconds_by_activity` accepts exact activity labels. Global keyed thresholds can target activities/edges anywhere in the dataset. Unknown process names or targets, non-finite values, negative durations and invalid percentages are rejected.

## Finding contract and interpretation

Every finding contains its stable ID, process ID/type, target entity, category, metric/unit, measurement type (`measured`, `approximation` or `observed_span`), observed value, baseline method/cohort/sample count/comparison/threshold, affected case count and severity.

Evidence contains the rule explanation, observation/case denominators, up to ten example observations with original source row numbers and explicit units, and caveats. Source row numbers count data records after the header. Repetition examples show extra event counts even when the finding metric is a percentage. Examples are bounded; affected-case counts cover the full eligible sample.

For individual timing outliers, the observed value is the mean of affected observations. For peer-mean outliers, it is the entire entity's mean and affected cases means cases exposed to that entity. Variant findings similarly count the entire flagged variant/status cohort. Workload findings report a member's measured total; evidence examples show contributing activity intervals.

`cause_status` is always `not_established`. Potential impact describes why to review the evidence. Where applicable, `observed_excess_seconds` sums positive excess over the reported threshold; it is not time proven avoidable or predicted improvement. Findings can overlap, so their excess values must not be added into a savings claim. `savings_estimated` is always false. No missing operational cause or improvement estimate is fabricated.

## Persistence and scope

Analytics is atomically stored beside the prepared log in `analytics.json`. Results bind the normalized checksum, validation revision and discovery analysis ID. Same input/options reuse the saved analysis. Changed discovery settings or remapping invalidate old metrics. Source/normalized file edits are detected. Case-status options therefore cannot silently diverge from discovery.

Mining and analytics share the per-server computation capacity and dataset locks. Direct POST requests run in FastAPI worker threads, returning when complete; busy computation gets an actionable 429. The frontend runs the full pipeline through [local background analysis jobs](frontend-workflow.md#background-jobs-and-recovery) and displays actual stage states. The local deployment assumes one backend worker with JSON storage, not a durable distributed queue. Models and assignment aggregates are loaded in memory; variant/finding pagination bounds response pages, not total computation memory.

The connected Overview, Process Explorer, Bottleneck Analysis and Process Variants pages display these real metrics and findings. Recommendations provides finding-linked review actions, measurement plans and caveats without estimated improvements; Case Explorer provides paginated source-event timelines. A fresh application URL starts empty. An explicit dataset URL restores the user's selection and follows its job, starting analysis when needed for missing or stale results. See [the frontend workflow guide](frontend-workflow.md) for routes, contracts and recovery behavior.

## Verification

From the project root, run:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests
.\backend\.venv\Scripts\python.exe -m ruff check backend/app backend/tests backend/scripts
.\backend\.venv\Scripts\python.exe backend/scripts/verify_analytics.py --dataset outputs/synthetic_hr_dataset/event_log.csv
```

The live check requires both local servers, uses the frontend proxy, and explicitly uploads the existing fixture plus a derivative subset with interval/assignment fields removed. It checks exact counts, durations, missing-data behavior and finding source-row evidence while verifying the source remains unchanged. Use `--base-url http://127.0.0.1:8000/api/v1` for a direct backend check. The source archive excludes fixtures; use `HR_TEST_EVENT_LOG` for the unit tests and `--dataset` for the live script when the existing CSV is elsewhere.
