# Documentation Evidence

These files are selected, lightweight records supporting Chapter 9. They are copies of previously generated evidence, apart from the explicitly identified documentation-review test reruns. They do not preload application state and are not a production dataset.

## Folders

- `tests/` contains the backend and frontend test outputs, production build output and refined-fixture rerun output from the documentation review.
- `browser/` contains the current compact-layout reports and the corresponding recorded browser verification scripts.
- `fixture/` contains the refined synthetic fixture's audits, upload/pipeline reports, historical interface reports, validation report and independent CSV-versus-API verification script.

## Reproduction boundaries

The browser scripts are preserved as execution evidence and may contain original machine-specific Playwright/runtime paths, localhost addresses, output paths and a saved dataset identifier. They are not installed test commands. To repeat them elsewhere, use an available Playwright installation, running frontend/backend services and the identifier returned by a fresh deliberate dataset upload, then adapt those environment settings. The application has no dependency on these scripts.

The independent pipeline verifier accepts a separately extracted dataset folder and an already analyzed dataset identifier. The CSVs are supplied in the separate synthetic-data archive, not this evidence directory. Historical reports may mention companion CSVs, saved analytics, manifests or screenshots from their original dataset package; those names are plain-text references, not claims that the full package is duplicated here.

The copied `validation_report.md` describes its original version 2 fixture evaluation. Its references to "this package" and to a saved localhost analysis relate to that original evaluation environment. Its historical interface checks predate the latest compact layout; the more recent `browser/` reports cover that layout. No runtime dataset or large screenshot collection is included in the project archive.

The reports establish technical consistency for tested synthetic inputs. They do not establish real university performance, causal bottlenecks, production capacity, security certification or numerical improvement from the suggested actions.
