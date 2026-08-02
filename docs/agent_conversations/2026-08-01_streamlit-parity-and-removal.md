# Streamlit parity and removal — session log

## Objective

Implement Phase 14: establish an honest desktop-parity gate, remove the retired Streamlit
runtime, and leave the native Qt application as the only supported interface.

## Baseline

Baseline commit: `c1ff068` (`docs(plans): scope phase 14 streamlit parity gate and removal`)
on `dev`, before creating `feat/streamlit-parity-and-removal`.

| Interpreter | Tier | Command | Measured result |
| --- | --- | --- | --- |
| Python 3.14.6 | DuckDB/default | `./run.sh uv run pytest -q` | `364 passed, 7 deselected in 15.03s` |
| Python 3.14.6 | Spark-selected | `./run.sh uv run pytest -q -m spark` | `7 skipped, 364 deselected in 1.60s` |
| Python 3.12.13 | DuckDB/default | `./run.sh uv run --python 3.12 pytest -q --no-cov` | `364 passed, 7 deselected in 8.32s` |
| Python 3.12.13 | Spark-selected | `./run.sh uv run --python 3.12 pytest -q --no-cov -m spark` | `7 skipped, 364 deselected in 1.10s` |

The Spark-selected runs were skipped on this host rather than passing. This is a measured
environment limitation, not a parity assertion; the CI Spark leg provisions Java and remains
an explicit post-removal verification target.

After the Python 3.12 measurements, the shared environment was restored with
`./run.sh uv sync --all-extras --dev --python 3.14`.

## Memory research

The required `memory_researcher` lookup found no indexed agent-memory records: its focused
queries returned `index_unavailable`, so this implementation relies on repository evidence and
does not use any memory claim to mark a parity criterion covered.

## Files modified

- `docs/agent_conversations/2026-08-01_streamlit-parity-and-removal.md`

## Tests added

- None in this baseline-only task.

## Design decisions

- Preserve the measured skipped Spark tier as a gap in host capability rather than presenting it
  as a passing result.

## Results

- The default DuckDB suite passed on Python 3.12 and Python 3.14 before implementation began.
