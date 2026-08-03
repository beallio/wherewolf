# Column profiling implementation

- **Date:** 2026-08-02
- **Objective:** Implement the committed column-profiling plan on `feat/column-profiling`.
- **Files modified:** domain models, DuckDB/Spark adapters, profile worker, catalog service,
  schema panel, preferences, main window, and focused tests.
- **Tests added:** mixed-type DuckDB profiling, Spark unsupported error, profile-worker lifecycle,
  schema-panel profile rendering, settings defaults, and source-staleness detection.
- **Design decisions:** DuckDB uses `SUMMARIZE` on a per-operation connection; approximate
  distinct is visibly labelled; VARCHAR numeric values remain empty; source snapshots make stale
  profiles explicit; automatic profiling is enabled below 256 MB.
- **Results:** `ruff`, whole-repository `ty`, and the full test suite passed (420 tests selected).
  Negative controls confirmed profile results and worker draining are guarded.
