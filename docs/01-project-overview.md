# 1 Project Overview

## Purpose and research context

The HR Process Mining and Improvement Platform is a local full-stack application for examining how recorded HR work actually progresses. It converts user-uploaded event logs into process models, case paths, timing summaries and evidence-linked improvement review actions. This documentation describes the implementation inspected on 9 November 2026, application version 0.1.0. It is intended to support an MSc software engineering submission, reproducible technical evaluation and continued development.

HR work often spans people, departments and systems. Aggregate counts alone do not explain which routes cases follow, where recorded time accumulates, or how often activities repeat. The platform addresses this visibility problem by reconstructing ordered case histories and comparing their observed behaviour. Its outputs support investigation; they do not establish causes or justify an operational change without domain review.

According to the supplied research brief, suitable operational HR event logs are not currently available from the university. Synthetic logs were therefore produced for development and testing. This availability statement is project context supplied by the researcher, not an independently audited institutional claim. The fixture represents Recruitment, Employee Onboarding, Leave Management and Monthly Payroll. Its literal process labels are `Recruitment`, `Onboarding`, `Leave Management` and `Payroll`.

**Research interpretation:** all reported fixture results demonstrate technical functionality on simulated data. They are not findings about GIU or any university's actual HR performance. The fixture names a fictional institution, Wadi Al-Nour University. Use of the supplied GIU logo in the interface is branding and does not turn simulated observations into institutional evidence. Validation against anonymized real HR event logs remains future work.

## Intended users and objectives

The primary users are HR analysts, business analysts and process improvement specialists. Researchers and developers also use the system to evaluate event-log quality, inspect reproducible calculations and test changes. These are conceptual actors, not implemented authorization roles; the application does not provide user accounts or role-based access control.

The objectives are to accept varied HR logs through editable column mappings; keep unrelated processes separate; discover models from actual uploaded events; expose interpretable performance, repetition and variant measures; connect findings to source evidence; and support cautious, human-reviewed improvement proposals. Process names, activity sequences and KPI values are not hardcoded for the fixture.

## Implemented scope

| Area | Current capability |
| --- | --- |
| Ingestion | Explicit CSV upload, bounded preview, editable mapping, timezone settings, actionable validation and confirmation |
| Preparation | Original attribute preservation, UTC normalization, deterministic event ordering and data-driven process separation |
| Mining | PM4Py directly-follows graphs, eligible Inductive Miner models, converted Petri nets and exact activity-sequence variants |
| Analytics | Observed case spans, processing intervals, measured or clearly labelled approximate waiting, repetitions, resource and department aggregates |
| Investigation | Process maps, timing comparisons, filtered findings, variant comparison and case timelines |
| Recommendations | Deterministic review actions tied to findings, suggested verification steps and explicit uncertainty |
| Management | Local file persistence, explicit dataset URLs, background job stages, retries and protection against stale results |

The five primary sections are Overview, Process Explorer, Bottleneck Analysis, Process paths (variants), and Recommendations. Case Explorer and Upload support these sections. A fresh URL opens an empty workspace; the application never automatically selects a development fixture. A saved dataset can be deliberately restored through its explicit URL parameter.

This is a local research application rather than a production HR information system. Authentication, dataset ownership enforcement, formal conformance checking, distributed durable workers and HR-system connectors are not implemented. Persistent files already exist; a managed historical analysis catalogue and retention controls do not.

## Synthetic dataset used for evaluation

The current refined fixture contains 4,700 events and 500 cases in a 52-column event log. It is supplied separately from the application. The accompanying case, employee, candidate, resource, department and calendar tables document simulated context. The application uploads one event-log CSV; it does not automatically join the supplementary files. Relevant attributes in the refined log were enriched offline.

| Literal process label | Cases | Events | Distinct activity sequences |
| --- | ---: | ---: | ---: |
| Recruitment | 100 | 1,255 | 22 |
| Onboarding | 100 | 1,092 | 16 |
| Leave Management | 150 | 953 | 7 |
| Payroll | 150 | 1,400 | 6 |
| Total | 500 | 4,700 | 51 |

The fixture is used to test upload and validation, process separation and discovery, performance arithmetic, repeated activity detection, variants, evidence links and recommendation presentation. It is not used as a startup dataset. The original and refined releases are retained separately, with change records and provenance checks. Test outcomes and their evidence are documented in Chapter 9.

## How to use this documentation

Chapter 2 specifies requirements and traceability. Chapters 3–6 explain architecture, pipeline, data and methods. Chapters 7–8 describe the REST contract and user workflow. Chapter 9 distinguishes newly executed tests from saved evaluation reports. Chapters 10–11 cover limitations and reproducible local setup. The accompanying Markdown sources retain editable Mermaid diagrams and links to the repository implementation.

## Implementation evidence

- [Application routes](../frontend/src/app/App.tsx) and [dataset selection](../frontend/src/features/datasets/DatasetContext.tsx).
- [Analysis state and explicit URL restoration](../frontend/src/features/analysis/AnalysisContext.tsx).
- [Backend entry point](../backend/app/main.py) and [package metadata](../backend/pyproject.toml).
- [Refined fixture evaluation](evidence/fixture/validation_report.md), copied here as evidence; the CSVs are distributed in the separate dataset package.
