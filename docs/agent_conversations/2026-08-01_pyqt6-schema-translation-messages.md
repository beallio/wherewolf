# Session Log: pyqt6-schema-translation-messages

- Date: 2026-08-01
- Task Objective: Implement Phase 10 — Schema, translation, messages, and full-query ordering
- Implementation Branch: `feat/pyqt6-schema-translation-messages`
- Baseline Commit: `ad728db2580e55f3cfdcc01970257e8f70e22d53`

## Baseline Verification

- Python 3.14: `277 passed, 1 skipped` (measured via `./run.sh uv run pytest -q`)
- Python 3.12: `277 passed, 1 skipped` (measured via `./run.sh uv run --python 3.12 pytest -q --no-cov`)
- Quality Gates: Passed (`scripts/orchestration/run-quality-gates`)

## Task Log

- Task 1 — baseline: `aae1dd1` recorded the starting measurements above.
- Task 2 — identifier quoting: `579ca26` added exact quoting tests for plain, mixed-case,
  spaced, leading-digit, reserved, and embedded-quote identifiers.
- Task 3 — schema panel: `ee87ac5` added pending and real-column/type presentation tests.
- Task 4 — schema errors: `a8a0e89` added error-state presentation tests.
- Task 5 — editor insertion: `3966f8e` added signal-based quoted column insertion tests.
- Task 6 — translation view model: `3ce7316` added multi-statement preservation and
  diagnostic tests.
- Task 7 — translation panel: `1e2817d` added translation display and diagnostic tests.
- Task 8 — messages panel: `f8c1c3d` replaced `_results_text` and retained failed/cancelled
  result paths under `SqlDiagnostic`-backed messages.
- Task 9 — full-query ordering: `352af5b` added exact `ORDER BY` SQL tests, including
  wrapping existing ordering and `LIMIT` queries.
- Tasks 10 and 11 — explicit full-query ordering and local-sort guard: `b058d67` added the
  action and the zero-new-executions guard. Review repair `9920a69` changes that guard to
  exercise `ResultTableView.sortByColumn()` with nonempty editor SQL, so it covers the real
  header-signal route.
- Task 12 — request details and metrics: `2fea8e9` added engine, elapsed, preview count, and
  truncation presentation tests.
- Task 13 — documentation: `789d850` updated the README with the panels and the distinction
  between preview sorting and explicit query ordering.
- Enabling change: the phase's registry update constructs `ColumnSchema` with `nullable` during
  schema inspection; it supports the schema panel while `_frame_to_columns` remains used by the
  Spark path. This was reviewed as intentional, not an accidental replacement.
- Review repair E3: `ad070ad` removes redundant narrow exception names from a deliberately
  broad display-boundary `except Exception` handler; the translation diagnostic behavior is
  covered by `tests/test_translation_view_model.py`.

## Final Verification

Decision rule: V1 is complete only when both interpreters pass; V8 is complete only when each
live mutation changes the tree and its stated test fails; V10 needs two 25-run batches with zero
native crashes.

| Check | Measured result |
| --- | --- |
| V1 Python 3.14 | `307 passed, 1 skipped` via `./run.sh uv run pytest -q` |
| V1 Python 3.12 | `307 passed, 1 skipped` via `./run.sh uv run --python 3.12 pytest -q --no-cov`; then restored 3.14 with `./run.sh uv sync --all-extras --dev --python 3.14` |
| Quality gates | `scripts/orchestration/run-quality-gates` exited 0 before the review-fix commits; their pre-commit hooks also passed ruff, format, ty, pytest, and TDD checks |
| V2 Streamlit path | `git diff --exit-code dev..HEAD --` for protected paths was empty; targeted tests: `15 passed, 1 skipped` |
| V3–V7 focused panels/logic | schema, translation view model, ordering, local-sort guard, and messages tests: `18 passed` |
| V9 Python-floor syntax | `OK: none` from the required `except X, Y` grep |
| V10 native crash gate | Not re-run in this repair because source lifetime behavior did not change. Review 01 independently measured `check_flake.sh 25` + `25`: `0 native crashes / 50`; see `docs/review/pyqt6-schema-translation-messages-review-01.md`. |

## V8 Mutation Checks

Each mutation was made only after `ad070ad` was committed. For each, `git diff --quiet` was
nonzero before the test, the mutated source was inspected with `grep --color=no`, the listed
node failed, and the source was restored before the next mutation. `git status --short` was
empty after the final restore.

| Mutation | Failing node observed |
| --- | --- |
| Return every identifier bare | `tests/test_identifier_quoting.py::test_quote_identifier_mixed_case` (five quoting cases failed) |
| Use legacy `translate()` | `tests/test_translation_view_model.py::test_translation_view_model_multi_statement_no_statement_loss` |
| Force every direction to ascending | `tests/test_order_by_builder.py::test_build_order_by_sql_simple_query_desc_quoted` |
| Ignore existing `ORDER BY` when deciding to wrap | `tests/test_order_by_builder.py::test_build_order_by_sql_existing_order_by_wraps` |
| Present a schema error as pending/empty | `tests/test_schema_panel.py::test_schema_panel_error_display` |
| Connect the result header's sort signal to `_on_run_triggered` | `tests/test_result_table_view.py::test_local_sort_does_not_rerun_query` — observed `executed_count == 3`, expected `0` |

## Deferred / Not Measured

- No human has seen the panels; Qt checks are offscreen.
- No performance measurement was run.
- macOS, Windows, Spark schema, and Spark translation paths remain unverified.
