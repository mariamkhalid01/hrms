# Process discovery API — milestone 3

The engine consumes only the confirmed canonical `normalized.jsonl` for a selected dataset. It does not read development CSVs, supplementary case tables, delay flags, rework flags or exception flags. Every partition comes from the uploaded `process_type` value. Without a mapped separation field, normalization creates one `Single process` partition. Case keys namespace the process and case ID, so reused IDs do not join unrelated workflows.

## Algorithms and selection

| Algorithm | Role in this implementation | Trade-off |
| --- | --- | --- |
| PM4Py directly-follows discovery | Always run; exact observed adjacent-event counts and trace boundaries | Faithful to adjacency, but a branch does not establish exclusive choice or concurrency; a cycle need not occur inside any single case |
| PM4Py Inductive Miner | Build a process tree from eligible ordered traces; default noise threshold 0 | Captures structured behavior and may generalize beyond the observations; explicit noise filtering can omit infrequent behavior |
| Process-tree to Petri-net conversion | Return places, transitions, arcs and initial/final markings | Includes silent transitions and structural arcs; observed DFG frequencies must not be assigned to Petri arcs |

These capabilities and the noise parameter follow the [PM4Py discovery API](https://processintelligence.solutions/app/pm4py/api/api/pm4py.discovery.html). Algorithm selection and the safeguards below are application policies, not claims that other logs are mathematically unmineable.

`auto` always returns DFG/variants and attempts induction when at least two eligible cases exist, at least one contains multiple events, and the partition has at most 50,000 eligible events and 100 distinct eligible activities. `inductive` relaxes only the two-case minimum. `dfg` skips induction. The event and activity safeguards apply to explicit requests too; they are configurable with `HR_INDUCTIVE_MAX_EVENTS` and `HR_INDUCTIVE_MAX_ACTIVITIES`, subject to validated hard caps. A skipped model carries a reason. A failed optional induction carries `status: "failed"` while preserving the genuine DFG and variants, and a repeat request retries it.

No fitness, precision, causality or business correctness is asserted by discovery alone. Zero-noise replay is covered by a focused test; dataset-wide conformance scoring is a later feature.

## Ordering and case status

Normalization sorts UTC timestamps within the namespaced case, breaks ties by the explicitly mapped source event order and then original data-row number, and assigns canonical `event_order`. Mining re-establishes timestamp → canonical event order → source row ordering and constructs PM4Py traces explicitly. It never lets a library's dataframe conversion silently reorder ties. Acknowledged duplicate rows remain events and can produce self-loops.

All observed cases participate in the DFG and variants, including known incomplete and cancelled cases. The start/end fields mean **first/last observed event**, not proven process opening or completion. A variant is the exact ordered activity sequence, including repeats; identical sequences share a variant even if their case statuses differ. Percentages use all observed cases in that process as the denominator.

By default, case status is `unknown`. Mapped event `status` and `outcome` fields are not case-completion evidence. To use a reliable case-level column retained among original attributes, explicitly supply both its name and value interpretation:

```json
{
  "algorithm": "auto",
  "noise_threshold": 0,
  "case_status_attribute": "Case completion",
  "case_status_values": {
    "Finished": "completed",
    "Still open": "incomplete",
    "Withdrawn": "cancelled"
  }
}
```

Values match after trimming and case folding. The attribute must exist. Blank values are ignored; missing/unrecognized values remain unknown. Multiple incompatible mapped states within a case become unknown and are reported as conflicts. This option is intended for a consistent case-level attribute, not changing event lifecycle statuses. Rejected cases can be mapped to completed or cancelled according to the analyst's explicit business definition.

Known incomplete and cancelled traces are excluded from Inductive Miner so their truncation/cancellation does not become an inferred normal completion. Unknown traces are included as observed examples, with a warning that their boundaries are assumed for induction. If no eligible cases remain, induction is skipped. DFG, variants and their status breakdowns still include every observed case. No incomplete case is inferred from its final activity's name, case length or synthetic flags.

## Timing and counts

- Activity `frequency` counts events; `case_frequency` counts distinct cases containing that activity; `repeated_case_count` counts cases containing it more than once.
- Transition `frequency` counts immediate adjacent pairs, including repeated traversals. `case_frequency` counts distinct cases containing that pair.
- `elapsed_time_seconds` measures consecutive canonical event timestamp differences. It is not labeled waiting time because a generic event timestamp may represent start or completion.
- `service_time_seconds` requires both mapped activity start and end. `inter_activity_gap_seconds` requires the preceding activity's end and following activity's start. Signed negative gaps are preserved and counted as overlaps.
- Durations are elapsed UTC seconds, not business hours. No synthetic processing/waiting columns are consulted. Each distribution includes sample count, mean, median, minimum and maximum. Missing interval evidence returns count 0 and null statistics, not fabricated zero durations.
- Variant average/median case duration is **last minus first observed event timestamp**. Single-event cases have an observed span of zero. `observed_duration_seconds` covers all member cases; `completed_duration_seconds` restricts the same span metric to explicitly completed cases. Even completed spans do not imply observation of work before the first event.

## JSON and React Flow

The versioned `DiscoveryResult` carries analysis/dataset/validation IDs, normalized-file SHA-256, PM4Py version, configuration, timestamp, computation duration, totals and independent process models. Full request/response types are in `app/schemas/discovery.py` and the generated OpenAPI schema.

Each process includes:

- Activities and DFG transitions with stable IDs derived from process/label content, frequencies and timing distributions.
- Observed start/end frequencies; alternative outgoing paths with traversal percentages; strongly connected graph-cycle groups; and separate evidence of actual within-case repetition.
- `react_flow.nodes` with labels, statistics and deterministic initial positions, plus `react_flow.edges` with stable source/target references, labels and statistics. The connected Process Explorer renders these in React Flow with Frequency, Performance and Rework modes, filtering and node/edge inspection.
- An optional recursive process tree with operator/label/silent fields, and a flattened Petri net with explicit initial/final tokens. Petri IDs are local to that serialized model because PM4Py can generate new internal names. Visible Petri transitions link to stable activity IDs. Petri arcs carry structural weights, not observation frequencies.
- Completion counts, ordering rules, timing/boundary definitions and relevant caveats.

Variants are fetched from the paginated endpoint instead of expanding every sequence in the main model response. Their IDs depend on process name and complete sequence, not rank or frequency. Results are ordered by descending case count, with a stable ID tie-breaker; pages default to 50 and cap at 200. The page carries `analysis_id` so clients can detect a new analysis while paging.

## Execution and persistence

POST `/api/v1/datasets/{dataset_id}/discovery` with `{}` after validation and processing. Read the response directly or GET the same URL later. Use its process ID for `/processes/{process_id}` or `/processes/{process_id}/variants?offset=0&limit=50`.

Direct discovery runs in a FastAPI worker thread, not in the browser or event loop. The request completes when its real result is saved. A per-server semaphore allows one active mining computation; other datasets receive an actionable 429 `DISCOVERY_BUSY`. Shared dataset locks prevent ingestion revisions from changing underneath discovery. Same-dataset operations serialize. The frontend uses the [local background analysis job](frontend-workflow.md#background-jobs-and-recovery), which runs discovery as part of the full pipeline and exposes actual stage states. The local queue is not durable across server restarts; cancellation remains future work.

Results are atomically stored in `discovery.json`, with variants, under the existing UUID dataset directory. Identical options and unchanged normalized data reuse the saved result through the direct discovery endpoint. A new background job intentionally reruns the complete pipeline. Remapping invalidates access until processing and discovery are repeated. Source and normalized checksums catch edited files; validation IDs bind results to the exact revision. New preparations record the normalized hash immediately; older milestone-2 preparations without that field establish a hash at first discovery. A fresh application URL selects no dataset or analysis; an explicit dataset URL restores that selection and can start analysis if results are absent or stale.

Local JSON storage and locks assume **one backend worker**. Large logs still require in-memory processing, and unusually large DFGs can produce large JSON models. Induction safeguards and variant pagination bound particular costs; they are not a production-scale memory guarantee. Distributed locking, server-side graph reduction, authorization, a database and durable distributed jobs remain separate deployment work.

## Verification

Run `python -m pytest` and `python -m ruff check app tests scripts` from `backend/`. Fixture checks read the external CSV only during explicit test execution. Set `HR_TEST_EVENT_LOG` when the existing development fixture is located elsewhere; the source archive deliberately does not package it.

With both servers running, execute `backend/scripts/verify_discovery.py --dataset <path-to-existing-event_log.csv>` using the backend virtual environment from the project root. By default it uses the frontend API proxy. Its independent counters and sequence/duration calculations check the combined file, an extracted single process without a process-type column, and that same process under an unseen label. The script uploads tests only when invoked and never rewrites the supplied file.
