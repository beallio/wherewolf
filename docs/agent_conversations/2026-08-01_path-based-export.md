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
