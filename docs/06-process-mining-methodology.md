# 6 Process Mining and Analytics Methodology

## 6.1 Analysis unit and evidence boundary

The analysis unit is a case within one explicitly identified process. The engine consumes normalized events ordered by timestamp, canonical event order and source row. It builds PM4Py traces with `concept:name` for activity labels and `time:timestamp` for UTC event instants. Process names, activity names and transitions come from the upload; the engine contains no fixed recruitment, onboarding, leave or payroll workflow.

Synthetic delay, rework and exception flags are not discovery inputs. Frequencies come from observed events and adjacency, variants from case sequences, and timing findings from timestamp calculations. Source attributes remain available for interpretation, but a flag is not accepted as proof of a bottleneck.

The methods support technical evaluation on simulated logs. They do not establish causal explanations or findings about actual university HR operations. Anonymized real logs and domain review remain necessary for operational validation.

## 6.2 Case completion and cohort rules

Case completion is optional and explicitly configured through a source attribute and a dictionary mapping source values to `completed`, `incomplete`, `cancelled` or `unknown`. Source values are trimmed and compared without case sensitivity. Both the attribute and value map must be supplied together. No automatic interpretation of event status as case status occurs.

A case receives a known state only when its nonempty mapped values resolve consistently. Missing values, unrecognized values or conflicting resolved states can result in `unknown`; conflict and unrecognized counts are reported. A closed rejected case may be mapped to `completed` when that matches the intended case semantics: completion measures closure, not a favorable business outcome.

All validated events, including acknowledged duplicates and explicitly incomplete or cancelled cases, remain in DFG frequencies, variants and general observed-duration metrics. Completed-only distributions are separately available. Inductive Miner excludes explicitly incomplete and cancelled cases. It includes unknown cases as observed complete examples, with a warning that true completion is not established.

The overall completion rate is returned only if all case states are known. Otherwise it is `null`. A known-status completion rate and status-coverage percentage remain available, allowing users to distinguish an observed subset from the entire process.

## 6.3 Directly follows discovery

The engine calls `pm4py.discover_dfg(log)` separately for every process partition. A directed edge A → B records an immediate succession of A and B within an ordered case. Edge frequency counts every occurrence of that adjacent pair. Edge case frequency counts distinct cases containing that pair. Activity frequency counts all occurrences; activity case frequency counts distinct cases containing the activity.

Start and end frequencies count observed first and last activities. They are observed boundaries, including those of partial and cancelled cases, rather than guaranteed formal start and end events. Alternative-path records are created when an activity has multiple distinct outgoing targets. Their percentages divide each edge frequency by all outgoing-edge occurrences from that source.

Self-loops are explicit. Strongly connected graph components identify groups participating in graph cycles. A cycle in an aggregate DFG is not proof that every member case repeated the whole cycle: different case orderings can contribute the edges. Likewise, branching does not prove an exclusive choice or concurrency. The interface therefore renders an observed process map with descriptive tasks and boundaries, not a claim of a fully inferred BPMN specification.

DFG discovery is the default descriptive foundation because it remains interpretable for sparse, incomplete and varied logs. Its limitation is representational: adjacency does not encode the full execution constraints of a formal workflow.

## 6.4 Inductive Miner and Petri net conversion

The discovery request supports `auto`, `dfg` and `inductive` algorithms; the default is `auto`. The DFG and exact variants are always computed. The optional additional model follows these rules:

| Eligibility check | Implemented behavior |
|---|---|
| Explicit `dfg` request | Skip Inductive Miner with an explanatory reason. |
| No eligible cases after excluding incomplete and cancelled cases | Skip. |
| Fewer than two eligible cases in `auto` mode | Skip. An explicit `inductive` request does not impose this particular two-case rule. |
| All eligible traces contain only one event | Skip. |
| Eligible events exceed `HR_INDUCTIVE_MAX_EVENTS` | Skip; default limit is 50,000. |
| Distinct eligible activity labels exceed `HR_INDUCTIVE_MAX_ACTIVITIES` | Skip; default limit is 100. |
| Remaining eligible log | Call `pm4py.discover_process_tree_inductive` with configured noise threshold and multiprocessing disabled. |

The discovered process tree is converted using `pm4py.convert_to_petri_net`. The response serializes tree operators, labels and children; Petri places, transitions, arcs and initial/final tokens are plain JSON. Raw PM4Py objects do not cross the API boundary. Petri arcs have no assigned observed frequency because their structural meaning differs from DFG adjacency counts.

The default noise threshold is zero; accepted values are at least zero and less than one. Nonzero noise filtering changes only the Inductive model, leaving DFG frequencies and exact variants unchanged. `dfg` requests cannot set a nonzero noise threshold. Inductive models can generalize beyond observed traces; the optional formal representation is not an exact replay catalogue. If discovery fails, the response records failure and retains usable DFG and variant output rather than substituting a predefined model.

The application does not perform conformance checking, alignment-based replay, fitness measurement or comparison with an uploaded expected workflow. A discovered Petri net alone does not establish that these functions exist.

## 6.5 Variant identification

`pm4py.get_variants_as_tuples` groups cases by the complete ordered tuple of observed activity labels. Two cases share a variant only if the label sequence, including repetitions and length, is identical. Resource, timestamp and duration differences do not create different variants.

Each variant reports a deterministic identifier, activity sequence and identifiers, case count, percentage of all cases in that process, observed-duration distribution, completed-case duration distribution and case-status counts. Variants are sorted by descending case count and then identifier. A variant percentage is calculated as 100 × variant case count / process case count.

Process, activity, edge and variant identifiers use a kind prefix and a truncated SHA-256 digest of deterministic JSON identity components. Equal labels in different processes therefore have separate activity identities. Duration comparisons across variants remain descriptive; they do not control for case complexity or establish which path caused a delay.

## 6.6 Timing definitions

All timing values use elapsed UTC seconds, including weekends, holidays and overnight periods. The application does not apply a working calendar to analytics. The synthetic business-calendar CSV supports fixture generation and offline audits, not automatic business-time calculation inside the platform.

| Metric | Calculation and interpretation |
|---|---|
| Observed case duration | Last canonical event timestamp minus first canonical event timestamp. A singleton case has a zero observed span. This excludes work before or after the recorded trace. |
| Full interval case duration | Maximum activity end minus minimum activity start, only for cases where every event has both interval endpoints. This is separately reported from the event-timestamp span. |
| Activity processing time | Activity end minus activity start for an event with both mapped timestamps. Missing intervals are unavailable, not zero. |
| Signed inter-activity gap | Next activity start minus previous activity end for an adjacent pair with the relevant endpoints. Negative values represent overlapping intervals. |
| Measured waiting metric | Nonnegative signed inter-activity gaps only. The interval is measured, but it is not proof of idle time or a queue: required waiting and unrecorded work may also occupy it. |
| Approximate waiting metric | Next event timestamp minus previous event timestamp when the adjacent interval pair is unavailable. This can include processing and other unobserved work. It is reported separately and explicitly labeled an approximation. |
| Activity incoming waiting | The applicable measured gaps and approximations for transitions entering that activity. It is distinct from the activity's own processing time. |

Distributions provide count, mean, median, minimum and maximum. Empty distributions contain zero count and null summary values. Processing coverage records the percentage of events with measured intervals. Waiting output records interval-pair count, approximation count and overlap count. Overlaps remain in signed-gap statistics and are excluded from nonnegative waiting statistics; the system does not convert negative intervals into invented waiting values.

Across all processes, the overall case-duration distribution is computed from individual case spans. It is not an unweighted average of process means. Completed-case duration is separately available where case states are identified.

## 6.7 Repetition and assignment measurements

A case repeats an activity when its label occurs more than once. The activity repeat rate divides repeating cases by cases containing that activity. Extra occurrences sum `count − 1` within those cases. A variant's repeated-activity count is sequence length minus the number of distinct labels; its extra-event percentage divides that count by sequence length. These observations identify repetition, not unnecessary work. Legitimate iterations and acknowledged duplicate records can both contribute.

Resource analysis uses `resource_id` when any values are available, otherwise `resource_name`. It does not fill missing resource IDs with names on individual rows. Department analysis uses the mapped department field. An absent field produces no corresponding assignment analysis.

For known assignments, the system reports event and case counts, activity diversity, event share, measured processing totals and coverage, repeated assignments within cases and repeated assignments to the same activity. Adjacent known values form comparable pairs; a changed assignment is a handover. Missing assignments are not bridged. Handover-per-case comparisons require complete assignment coverage for the case.

Summed processing intervals are observed workload, not utilization, productivity or capacity. Overlapping work can be counted more than once, and the dataset may omit other duties. Resource findings require scrutiny of role, availability and case mix before any staffing conclusion.

## 6.8 Bottleneck thresholds and evidence rules

Thresholds are configurable through the analytics API, including process-specific overrides and selected activity or transition limits. The current frontend does not provide a general threshold editor. Unknown process, activity or transition targets are rejected rather than silently ignored.

Without an explicit business limit, the statistical upper threshold is:

`max(Q3 + iqr_multiplier × (Q3 − Q1), median × minimum_relative_increase)`

Quartiles use linear interpolation. Defaults are five minimum samples, two minimum affected cases, an IQR multiplier of 1.5 and a minimum relative increase of 2. These are implemented screening defaults, not validated institutional service-level targets. A business threshold can be applied without the statistical minimum-sample rule, but the applicable affected-case requirement still remains.

| Finding category | Actual detection rule |
|---|---|
| Long processing | Evaluate activity intervals against their own upper fence or configured limit. If too few cases exceed it, an activity with enough observations may instead be flagged when its mean exceeds the robust upper fence of sufficiently sampled activity means in the same process. |
| Long waiting | Apply the same duration logic to transition gaps. Measured gaps and approximations are assessed separately. A configured transition limit overrides the general waiting limit. |
| Repeated activity | At least the configured number of affected cases and a repeating-case percentage strictly above the screening limit; default is 20%. |
| Rework-heavy path | At least the configured number of cases and a variant extra-event percentage strictly above the screening limit; default is 20%. |
| Delayed cases | Observed spans strictly exceed the process threshold within the same case-state cohort; at least the configured number of cases is required. A statistical outlier is not automatically a missed SLA. |
| Slow variant | The mean span of a variant within a case-state cohort exceeds the corresponding same-process, same-state case threshold; the cohort must meet the affected-case minimum. |
| Frequent handovers | Handover counts for cases with fully observed assignments exceed the process-specific statistical or business threshold. |
| Workload imbalance | Total measured processing exceeds a robust peer threshold, with full timing coverage and enough involved cases. Resources with multiple identified roles are excluded; single-role resources are compared within role, and unspecified roles form their own cohort. Department totals are compared as department assignments. |

Duration-rule peer fallback is used only when no business threshold is specified. It requires sufficient peer means and sufficient observations for the target. Activity frequency alone never triggers a bottleneck finding.

## 6.9 Finding interpretation and recommendation generation

A finding includes a stable ID, process, entity, category, metric and unit, measurement type, observed value, baseline method and cohort, threshold, affected-case count, severity, evidence samples and potential impact. For duration outliers the observed value is the mean of the affected observations, or the whole entity mean when the peer fallback is used. Evidence includes eligible and affected observation counts and up to ten example cases with source-row references.

Severity is based on the ratio between the observed value and threshold: high at a ratio of at least 2, medium at least 1.25, otherwise low. With a zero threshold the implementation uses a ratio of 1.5. A high-severity approximation is capped at medium. Findings are ordered by severity, affected-case count and identifier.

For selected timing findings, observed excess seconds sum time above the comparison threshold. This is descriptive exposure, not predicted savings. Findings can overlap, so excess values must not be summed into a promised improvement. The response explicitly reports that causes are not established and savings are not estimated.

The recommendation engine creates one deterministic review recommendation per finding. Its category selects a title, three review actions and a measurement plan; priority follows finding severity and the finding ID remains attached. Suggestions ask the analyst to inspect evidence, confirm context and only then pilot a change. There is no generative model, causal diagnosis, automatic HR intervention or calculated expected improvement.

## 6.10 Implementation traceability

- [Trace construction and case states](../backend/app/services/discovery/log.py), [discovery algorithms](../backend/app/services/discovery/engine.py), [model serialization](../backend/app/services/discovery/serialization.py) and [variants](../backend/app/services/variants/engine.py).
- [Timing primitives](../backend/app/services/analytics/measurements.py), [performance aggregation](../backend/app/services/analytics/engine.py), [assignment analysis](../backend/app/services/analytics/resources.py) and [analytics contracts and threshold defaults](../backend/app/schemas/analytics.py).
- [Bottleneck rules](../backend/app/services/bottlenecks/engine.py), [recommendation rules](../backend/app/services/recommendations/engine.py), [discovery options](../backend/app/schemas/discovery.py) and [configured eligibility limits](../backend/app/core/config.py).

