# Technical Documentation Index

This directory documents the implemented HR Process Mining and Improvement Platform for an MSc software engineering project. The review covers the current React frontend, FastAPI backend, PM4Py discovery, performance analytics, evidence rules, API contracts and available tests. It distinguishes implemented capabilities, bounded or partial capabilities, and proposed enhancements.

**Research boundary:** the available HR evaluation data is synthetic. It simulates four HR processes for development and controlled technical verification. The results are not findings about GIU or any university's actual HR operations. Real operational validity requires a separate study using governed, anonymized HR logs.

## Chapters

| Chapter | Scope |
| --- | --- |
| [1 Project overview](01-project-overview.md) | Problem, objectives, users, scope and synthetic research context |
| [2 System requirements](02-system-requirements.md) | Functional and quality requirements, status, acceptance criteria and traceability |
| [3 System architecture](03-system-architecture.md) | Frontend/backend responsibilities, service boundaries, storage and communication |
| [4 System pipeline](04-system-pipeline.md) | Upload to validation, normalized events, mining, analytics and recommendations |
| [5 Data model](05-data-model.md) | Canonical event fields, provenance, identifiers and persisted artifacts |
| [6 Mining and analytics methodology](06-process-mining-methodology.md) | Discovery, variants, timing semantics, thresholds, resource analysis and limitations |
| [7 API documentation](07-api-documentation.md) | Actual REST operations, inputs, outputs, error behavior and examples |
| [8 Use cases](08-use-cases.md) | Actors, workflow, exploration and evidence review |
| [9 Testing and evaluation](09-testing-and-evaluation.md) | Newly executed checks, retained reports, test scenarios and unverified areas |
| [10 Limitations and future work](10-limitations-and-future-work.md) | Operational risks, current boundaries and proposed enhancements |
| [11 Installation and deployment](11-installation-and-deployment.md) | Dependencies, environment configuration, local run and verification commands |

## Diagrams and API reference

The diagrams are embedded as Mermaid source in their respective chapters and retained as editable files:

- [System architecture](diagrams/architecture.mmd)
- [End-to-end pipeline](diagrams/pipeline.mmd)
- [Use-case relationships](diagrams/use-cases.mmd)
- [Captured OpenAPI specification](reference/openapi.json)

The OpenAPI file is a captured contract, not a running backend. For a running local server, interactive documentation is available at `http://127.0.0.1:8000/api/docs`. The accompanying Word document presents the same technical material with rendered diagrams; it is supplied separately.

## Verification context and evidence

The documentation review reran 135 backend tests, four fixture-specific tests against the refined dataset, 26 frontend tests and the frontend production build. The four fixture checks repeat existing test functions under the refined input; they are not additional unique suite tests. Recorded browser and independent fixture reports are identified separately from these reruns in Chapter 9. No load benchmark, penetration test, formal accessibility study or evaluation of real university HR records is claimed.

Selected lightweight evidence is retained inside [evidence](evidence/README.md): test logs, browser reports and scripts, fixture audits and the historical fixture validation report. Paths in the chapter links resolve within the project package or its source tree. Test logs may retain the original local filesystem paths from the execution environment.

## Package boundaries

The project archive contains application source, dependency declarations, environment examples, tests and this documentation. Dependency installations, local virtual environments, generated frontend bundles, runtime uploads, saved analyses, scratch work and dataset CSVs are excluded. Install dependencies and start the services as described in Chapter 11.

The synthetic dataset is delivered in a separate archive. Extract it wherever convenient and explicitly upload its `event_log.csv`; its supplementary CSVs support dataset documentation and audits and are not automatically joined by the application. The application starts empty. Saved dataset identifiers appearing in retained evidence belong to the original test environment and will not exist in a clean installation. A fresh upload creates a new identifier.

Repository source links in these chapters are intended for the complete project archive. A documentation-only copy retains the narrative, diagrams, API snapshot and evidence but needs the project source alongside it to resolve links beginning with `../frontend/` or `../backend/`.
