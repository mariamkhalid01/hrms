# Validation and application test report — version 2.0

**Result: passed.** The refined synthetic CSV was uploaded through the application's normal browser workflow, mapped, validated, confirmed and processed by its actual Python/PM4Py backend on 9 November 2026. These are results for **Wadi Al-Nour University (fictional)**, not actual GIU or university HR performance.

## Dataset and provenance

- 4,700 events, 500 cases, 52 event-log columns and four independent processes.
- Original CSVs remain unchanged in the separate `synthetic_hr_dataset` release; their SHA-256 hashes reconcile with the repair audit.
- 39 responsible-person assignments corrected: 35 ordinary duties during recorded approved absence and four self-review/decision assignments.
- Seven event-scoped delegations preserve the person's real directory role. Finance Officers retain payment execution, separate from approval.
- Ten intervals in five payroll cases move by 12–110 minutes to fit full-duration qualified staffing slots and downstream dependencies. All activity durations, event orderings and case dispositions remain unchanged.
- One overlapping annual-leave period is moved with the same working-day length and balance deduction. Thirteen dependent handoff flags are recomputed.
- Case status, pending work, cutoff, readable names, actor/owning department distinction and selected HR context are now included in the uploaded file.

Every exact correction is recorded in the change CSVs. No new case, event, activity branch or dramatic delay was added to improve the appearance of a map. The standalone `synthetic_hr_event_log_v2.csv` is identical to this package's `event_log.csv`.

## Validation layers actually executed

| Check layer | Result | Saved evidence |
| --- | --- | --- |
| Deterministic repair verification | 25 checks passed | `repair_validation.json` |
| Independent structural/business audit of final CSVs | 91 checks passed | `business_consistency_audit.json` |
| Independent provenance, joins and repaired-availability audit | 22 checks passed | `provenance_audit.json` |
| Normal browser upload, mapping, confirmation and real job | 14 checks passed | `upload_test_report.json` |
| Independent source-CSV versus live API arithmetic/evidence | 4,702 checks passed | `pipeline_assessment.json` |
| Interactive map tests | 25 checks passed | `process_map_test_report.json` |
| Desktop/mobile frontend integration | 37 checks passed | `frontend_integration_report.json` |
| Outcome-aware case/UI checks | 31 checks passed | `case_ui_test_report.json` |
| Frontend unit tests | 26 passed across four test files | `frontend_build_report.json` |
| TypeScript and production frontend build | Passed | `frontend_build_report.json` |

The checks overlap in purpose; these counts should not be interpreted as independent statistical observations. Browser tests reported no JavaScript errors. No backend mining algorithm or HR workflow was hardcoded for this fixture.

The application validator reported **zero blocking errors, zero warnings and one informational category**: optional Cost is unmapped. Missing cost does not prevent analysis. All original attributes remain available. The final serialized CSV's timestamps were explicitly checked as ISO 8601 text with their original offsets; normalization stores the same instants in UTC.

## Normal application workflow

A fresh session started empty. The upload used `synthetic_hr_event_log_v2.csv`, showing 4,700 rows and 52 columns. Resource Name was mapped to `resource_name`, Department to `department_name`, Activity Start/End to the recorded lifecycle columns, event Status to `activity_status`, and event order to `event_order`. Full mappings are saved in `application_validation.json` and `generation_manifest.json`.

The optional generic case-outcome setting was configured explicitly: `case_status` values Completed and Rejected → finished; Incomplete → still open; Cancelled → cancelled. This is user-supplied interpretation, not a built-in rule. Rejected means a terminal negative decision, not an approved or successful request. Without such configuration, completion stays unknown.

All eight real background stages completed: reading, validating, normalizing, separating processes, discovering models, calculating performance, detecting bottlenecks and preparing recommendations. The browser observed queued, running and completed server states; no fabricated percentages were used.

Saved dataset ID: `cbd64c13-9b05-42e0-86d2-c0cd2fba1a12`.

Open the saved analysis while the local servers are running:

http://127.0.0.1:5173/process-explorer?dataset=cbd64c13-9b05-42e0-86d2-c0cd2fba1a12

## Actual discovery, paths and timing

PM4Py **2.7.23.12** discovered DFGs and Inductive Miner models, with serialized process trees and Petri nets, from the uploaded events. The visualization uses observed adjacency and counts; an apparent DFG branch is not proof of an exclusive business decision or concurrent execution. Inductive models can generalize beyond the observed traces. The saved `discovery.json` contains the exact algorithms, input-cohort metadata, activities, transitions, loops, alternatives and frequencies.

| Process | Cases | Events | Activities | Transitions | Exact paths | Repeated-label cases | Mean observed span (days) | Median span (days) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Leave Management | 150 | 953 | 12 | 14 | 7 | 9 | 1.947 | 0.939 |
| Onboarding | 100 | 1,092 | 16 | 21 | 16 | 11 | 10.484 | 10.150 |
| Payroll | 150 | 1,400 | 13 | 15 | 6 | 15 | 10.763 | 10.937 |
| Recruitment | 100 | 1,255 | 21 | 29 | 22 | 9 | 21.793 | 22.094 |

The 51 activity sequences and all activity/transition/path frequencies match the original. The four most common displayed paths reconcile exactly to the actual API sequences. Rare paths remain visible and filterable; no cases were duplicated to increase their weight.

All 4,700 processing intervals reconcile to end minus start. All **4,200 consecutive gaps are measured end-to-next-start intervals**, with zero approximated pairs and zero overlaps. Observed case span is last completion minus first completion, not first start to last end. Across all cases its mean is 887,175 seconds and median 858,360 seconds. Only the audited intraday payroll changes alter the source timing aggregates.

These are elapsed calendar durations. The companion `waiting_business_minutes` values also reconstruct against the retained working calendar, but the app's elapsed gaps are not silently relabeled as business time. Unfinished cases retain observed partial spans and no invented finish.

Explicit case interpretation yields **483 finished terminal decisions, 12 incomplete, five cancelled and zero unknown**. The 483 includes 14 rejected cases; it is a closure measure, not a success rate. Original case dispositions remain 469 Completed, 14 Rejected, 12 Incomplete and five Cancelled. Completed-only duration cohorts reconcile independently.

## Findings, rework and recommendations

The backend generated **62 evidence-based findings and 62 linked review recommendations**: 42 long-gap findings, six long-processing findings, nine workload-distribution findings, one repeated-activity finding, two rework-path findings and two delayed-case findings. Counts were outputs of the configured rules, not generation targets.

The independent verifier recalculated frequencies, case spans, processing/gap distributions, repeated sequences, actor/department aggregates, thresholds and **442 supporting source evidence samples**. It used raw event rows and normal API results without importing the application mining engine or using delay/rework/exception flags as its discovery mechanism. Recommendations remain review actions linked to measured findings; they do not assert proven causes or numerical improvements.

Useful demonstrations include alternative recruitment routes, onboarding document resubmission, payroll correction/reverification loops, rejected/cancelled paths and visibly unfinished cases. Different path durations can be compared while preserving their cohort sizes. A repeated label alone is not proof of unnecessary rework, and a one-time correction need not repeat a label.

## Visual and interaction inspection

All five main sections and the supporting Case Explorer were checked at desktop and mobile widths. Common-path and all-path diagrams, optional counts, time/repeated-step overlays, route filtering, fit, step-detail popups, finding filters/evidence, full path sequences, path-to-case navigation and recommendation review dialogs worked with this uploaded analysis. Screenshots are saved in `visual_evidence`.

The common-path view remains the clearest introduction. The full recruitment graph exposes its 21 activities and 29 transitions; low-frequency returns make it denser, so route filtering and focused paths remain useful. No extra branches were added to make it visually complicated.

Case `LEV-0053` demonstrates correct censoring: two observed events carry Completed activity status, while the popup identifies the case as incomplete. Recorded details retain `case_status=Incomplete` and `pending_activity=Manager Review`. Named resources and actor departments are displayed; no unobserved Manager Review event is drawn. Popup keyboard focus, Escape dismissal and mobile fit passed.

## Limits and remaining work

The original already had sufficient variation for development testing. Refinement improves consistency and interpretation, not empirical realism beyond the documented assumptions. Only 19 of 51 paths have at least five cases; 32 rare paths cover 46 cases and should not support strong statistical claims. No real university data validates the simulated distributions.

Long payroll approval-to-payment gaps often include intentional waiting for the modeled pay date. All 147 observed payment dates retain their classifications: 144 on target and three late. Calendar closures account for much elapsed waiting. These facts limit any claim that a measured gap is removable waste.

Resource assignment totals describe this sample, not institutional utilization or causal overload. Fixed process-family generation order, per-step actor sampling, partial availability records, sequential single-actor intervals and a limited explicit authorization model remain disclosed. Full reporting hierarchy, team/concurrent work and an empirically calibrated queue model are outside the fixture.

The application remains generic and starts empty. The only product addition for this audit is optional, explicitly configured case-outcome interpretation in the mapping/confirmation flow. Dataset-specific assumptions, names, sequences and metric values remain outside production application code. Future calibration requires real observations; increasing synthetic complexity alone would not establish real operational findings.
