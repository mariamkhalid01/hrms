# 10 Limitations Risks and Future Work

## Research validity

The evaluation uses synthetic logs. It establishes that the implemented pipeline can ingest, validate, discover and calculate results for controlled inputs; it does not establish that the simulated distributions, workloads or delays represent real university operations. The supplied research brief states that suitable university HR event logs are currently unavailable. Future research should obtain appropriate institutional approval, minimize and anonymize personal data, and assess the completeness and provenance of real logs before analyzing them.

The fixture includes four families of HR work but cannot cover every organizational workflow. Recruitment cases represent requisition-level activity rather than a complete candidate-level funnel, while payroll cases represent departmental batches and adjustments. A case identifier defines the unit of analysis: comparisons become misleading when unlike units are pooled without explanation. Rare paths also have weak empirical support; the refined fixture contains 51 paths, of which only 19 have at least five cases.

## Measurement and interpretation risks

| Limitation | Consequence and current mitigation |
| --- | --- |
| Partial or incomplete observation | Observed case span is not necessarily full cycle time. Configured case states and completed-only cohorts help interpretation; unknown states remain unknown. |
| Missing lifecycle timestamps | Processing time cannot be measured. Consecutive event timestamps provide an explicitly labelled waiting approximation, not an exact queue measurement. |
| Calendar time | Elapsed durations include nights, weekends and planned waits. The application does not automatically use the supplementary business calendar. |
| Overlapping intervals | Interleaved work can invalidate simple sequential waiting assumptions. Overlaps are exposed separately rather than turned into negative waiting. |
| Data quality | Duplicate observations are reported and preserved. Misidentified cases, missing events or inaccurate timestamps can still distort discovery even if a file is structurally valid. |
| DFG interpretation | Adjacency is observed order, not proof of causality, exclusive decisions or parallel work. A path assembled from graph edges need not have occurred as a complete trace. |
| Repetition interpretation | A repeated activity label can describe a legitimate review cycle. Repetition is evidence of recurrence, not proof of unnecessary work. |
| Resource context | Recorded assignments are event involvement, not utilization or available capacity. Missing attributes suppress corresponding metrics; the sample may omit other duties. |
| Statistical screening | Thresholds identify unusual recorded values relative to their cohort. Small samples, mixed case complexity and skew can affect findings; business thresholds and expert review remain relevant. |
| Recommendations | Rules propose review actions from findings. They do not establish causes, quantify guaranteed benefit or automatically implement changes. |

In the synthetic payroll scenario, many approval-to-payment gaps include an intentionally scheduled pay date. Treating the whole gap as removable waste would be incorrect. Likewise, a rejected case can be a finished terminal decision without being a successful application. These examples show why operational meaning must accompany the numerical output.

## Engineering and deployment limits

The backend persists uploaded files and current results on the local filesystem. This provides local persistence, not a transactional multi-user data platform or versioned historical catalogue. In-memory locks and the job worker assume one backend process. Recorded job files do not make execution durable: interrupted jobs require retry after restart. Normalization and analysis use in-memory Python structures, so configured upload and discovery bounds are safeguards rather than evidence of large-scale capacity.

The application has no authentication, authorization, tenant ownership model, rate-limiting framework, encrypted storage management or retention/deletion workflow. Its CORS allowlist and sanitized errors are useful controls but are not access control. A dataset UUID is an identifier, not an authorization secret. Real identifiable HR data should not be introduced into a shared deployment without a separate security and governance design.

The browser evidence covers selected desktop/mobile sizes in the local environment. It is not a full browser/assistive-technology compatibility study. No formal usability study with novice analysts, production load benchmark, penetration test, recovery exercise or real-university operational evaluation has been completed as part of this documentation audit.

## Proposed enhancements

| Priority | Proposed work | Relationship to current implementation |
| --- | --- | --- |
| High | Validate with anonymized real HR logs and domain experts | Extends synthetic technical validation to external operational validity. |
| High | Authentication, ownership controls, retention and deployment hardening | Adds controls absent from the local research application. |
| High | Durable queue and transactional metadata storage | Replaces single-process worker assumptions; files already persist today. |
| Medium | Versioned dataset and analysis catalogue | Adds history, search and deliberate lifecycle management to existing saved snapshots. |
| Medium | Business-calendar and schedule-aware interpretation | Extends elapsed-time analysis with explicitly configured working periods and planned waits. |
| Medium | Conformance checking against approved HR models | New capability; current discovery does not compare actual logs to a normative model. |
| Medium | Deeper recommendation evaluation | Tests review actions with experts and measured outcomes; avoids attributing hypothetical benefits to current rules. |
| Medium | HR-system integrations | Adds secure extraction and refresh mechanisms beyond explicit CSV upload. |
| Medium | Accessibility and novice-user studies | Complements implemented keyboard/responsive features with systematic user evaluation. |
| Low | Additional discovery and object-centric approaches | Investigates cases involving multiple related business objects; algorithms must be selected for actual log semantics. |

These are proposals, not commitments or implemented functions. Their priority is an engineering assessment for future planning, not an empirically validated organizational ranking.

## Evidence

See [configuration](../backend/app/core/config.py), [application composition](../backend/app/main.py), [analysis job service](../backend/app/services/orchestration/jobs.py), [fixture validation and limitations](evidence/fixture/validation_report.md), and the detailed methodology and testing chapters.
