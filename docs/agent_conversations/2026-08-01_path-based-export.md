# Path-based export implementation session

Date: 2026-08-01

## Objective

Implement Phase 12 path-based export from
`docs/plans/2026-08-01_path-based-export.md`.

## Baseline

Base commit: `b25485b` (`docs(plans): scope phase 12 path-based export`).

- Python 3.14: `334 passed, 1 skipped, 1 warning in 20.74s` from
  `./run.sh uv run pytest -q`.
- Python 3.12: the required `./run.sh uv run --python 3.12 pytest -q --no-cov`
  command exited successfully in the baseline batch; its output was truncated by the
  command capture before the tally could be recorded. Exact tally: not measured.
- The development environment was restored with
  `./run.sh uv sync --all-extras --dev --python 3.14`.

## Decision record

The selected format controls the suffix; a mismatched suffix is replaced. Writes use a sibling
temporary file followed by `os.replace`, so failed writes preserve an existing destination.
Selection order is shared with the clipboard path. Full XLSX is capped at 100,000 rows because
the available XLSX writer is not streaming; source mutations warn but do not block a requested
export.

## Measured results

- Targeted export tests: `38 passed in 1.42s` (Python 3.14).
- Full quality-gate run after implementation: `346 passed, 1 skipped, 1 warning in 20.58s`
  (Python 3.14); Ruff formatting and `ty check src/` passed.
- Python 3.12 verification: `346 passed, 1 skipped, 1 warning in 14.32s`; the shared
  development environment was then restored to Python 3.14.
- Not measured: mutation checks V8, two 25-run native-crash batches V11, a real-window manual
  export, multi-gigabyte memory use, Spark export, macOS and Windows dialogs. Full streaming is
  structurally exercised by DuckDB COPY output tests, not a large-scale memory measurement.

## Review round 01 resolution

- Added a request-scoped DuckDB connection spy that requires `COPY ... TO` and traps
  `.pl()`, `.arrow()`, `.fetchall()` and `.df()` on the full-export path.
- Export workers now wait until their cancellation handle reaches the controller before export
  work starts. Cancellation tests preserve an existing destination byte-for-byte, leave no
  temporary file, surface failures as terminal results, and make cancellation after completion
  safe.
- Moved the visual selection rules into `services/selection.py`; both clipboard serialization and
  preview export use that one implementation. The moved/hidden/discontiguous selection test is
  in `tests/test_selection.py`.
- The required memory search returned no indexed claims or claim IDs: the project memory import is
  still pending. No historical claim informed this round; implementation was revalidated from the
  current repository and committed plan.

### V8 mutation checks

Each mutation was applied to a committed tree, confirmed by a non-empty `git diff`, grepped with
`--color=never`, tested, and reverted before the next mutation.

1. Replaced `COPY` with `con.sql(...).pl()` plus Polars writes: `tests/test_full_export.py::test_full_export_issues_copy_without_materialising_result` failed for both `csv` and `parquet` with the `.pl()` materialisation trap.
2. Wrote directly to the destination: `tests/test_export_destination.py::test_atomic_writer_preserves_existing_bytes_and_removes_temp` failed because `b"partial"` replaced `b"original"`.
3. Ignored visual column mapping: `tests/test_selection.py::test_selected_frame_uses_moved_visible_columns_for_discontiguous_cells` failed with `['a', 'hidden_b']` instead of `['c', 'a']`.
4. Skipped extension normalisation: `tests/test_export_destination.py::test_destination_normalisation_and_filter_are_format_driven` failed with `out` instead of `out.csv`.
5. Left the temporary file behind on error: `tests/test_export_destination.py::test_atomic_writer_preserves_existing_bytes_and_removes_temp` failed on the remaining `.out.csv.*` file.
6. Treated cancelled save-dialog output as a path: `tests/test_file_dialog_service.py::test_qt_export_dialog_cancellation_returns_none_without_creating_destination` failed with `ValueError` for `Path('.')`. This was re-run after committing the new cancellation test.

### Final verification

- Python 3.14: `352 passed, 1 skipped, 1 warning in 23.68s` from the final quality-gate suite.
- Python 3.12: `352 passed, 1 skipped, 1 warning in 14.65s`; restored afterwards with `./run.sh uv sync --all-extras --dev --python 3.14`.
- `scripts/orchestration/run-quality-gates`: passed; review-note deletion check passed; protected
  Streamlit/export diff against `dev` was empty; V9 reported `OK: none`.
- V11: `scripts/check_flake.sh 25` passed twice with `0 native crashes in 25 runs`; the final
  per-run logs are preserved at `/tmp/wherewolf/flake-guard-run-1.txt` and
  `/tmp/wherewolf/flake-guard-run-2.txt`.
- Still not measured: a real-window manual export, multi-gigabyte memory use, Spark export, and
  macOS/Windows dialog behavior. Streaming remains structurally verified, not memory-measured.
