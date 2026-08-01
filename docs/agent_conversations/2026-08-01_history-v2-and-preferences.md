# History v2 and persistent preferences — implementation session

Date: 2026-08-01

## Objective

Implement Phase 11 from `docs/plans/2026-08-01_history-v2-and-preferences.md`.

## Baseline

- Base commit: `6bb731a` (`docs(plans): scope phase 11 history v2 and persistent preferences`).
- Python 3.14: `307 passed, 1 skipped, 1 warning in 20.72s`.
- Python 3.12: `307 passed, 1 skipped, 1 warning in 14.38s`.
- Both baseline commands used `HOME=/tmp/wherewolf/home` so default history writes stay in the
  permitted temporary workspace. The initial unmodified 3.14 attempt without that isolated
  home failed with six test failures and one Qt teardown error because `/home/beallio/.wherewolf`
  is read-only in this sandbox; its output is retained at `/tmp/wherewolf/baseline-3.14.log`.

## Planned validation

- Run the plan's full quality gates and both-interpreter suite after implementation.
- Run the required mutation checks after committing the implementation.
- No human desktop verification, real-user-history migration, performance test, macOS test, or
  Windows test is planned for this Linux/offscreen session.

## Implementation

- Added schema-v2 history records with UUIDs, on-read v1 migration, per-record validation,
  UUID lookup, and preserved atomic writes in `storage/history.py`.
- Added a UUID-backed History dock that restores SQL without executing it, restores available
  catalog files, and reports missing files.
- Added safe settings fallback, restored desktop layout coverage, and Reset Layout / Clear History
  actions.

## Measured results

- Python 3.14 final suite: `333 passed, 1 skipped, 1 warning in 21.01s`.
- Python 3.12 final suite: `333 passed, 1 skipped, 1 warning in 14.67s`.
- The 3.12 run used `--no-cov`; the environment was then restored with
  `./run.sh uv sync --all-extras --dev --python 3.14`.
- V8 mutation checks failed at their intended node IDs:
  - `tests/test_history_dock.py::test_history_dock_selects_duplicate_labels_by_stable_id`
  - `tests/test_history.py::test_new_entries_have_versioned_stable_ids_and_streamlit_keys`
  - `tests/test_history.py::test_malformed_records_are_isolated_from_valid_history`
  - `tests/test_history.py::test_v1_history_migrates_all_records_in_order_and_only_once`
  - `tests/test_history.py::test_record_cap_evicts_the_oldest_v1_record_after_migration`
  - `tests/test_settings_service.py::test_settings_service_each_corrupt_value_falls_back_to_its_default[completion_enabled_key-false-restore_completion_enabled-True]`
- `closeEvent` was not changed, so V10 was not applicable. No human desktop test, real-user
  migration, performance measurement, macOS test, or Windows test was run.

## Review round 01 follow-up

- Added an autouse pytest fixture that redirects the default `HistoryManager` path and both
  QSettings user-scope backends to each test's `tmp_path`.
- Added a bare-`MainWindow` regression test that failed before the fixture because construction
  initialized `/home/beallio/.wherewolf/history.json`; it now asserts the history and QSettings
  paths are test-local.
- Focused fixture regression group: `30 passed in 0.24s`.
- Python 3.14 full suite: `334 passed, 1 skipped, 1 warning in 21.76s`.
- `scripts/orchestration/run-quality-gates`: exit 0 (`334 passed, 1 skipped, 1 warning in
  22.00s`).
- Python 3.12 full suite with `--no-cov`: `334 passed, 1 skipped, 1 warning in 14.96s`.
- Restored the shared environment with `./run.sh uv sync --all-extras --dev --python 3.14`.
