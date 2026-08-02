# Release candidate — session log

## Objective

Implement Phase 15: make the desktop migration distributable, document its actual workflow,
and prepare a release candidate for the maintainer's manual acceptance gate. This phase does not
bump the version, promote `dev`, tag a release, or sign off the manual checklist.

## Baseline

Baseline commit: `3a37d5a` (`docs(plans): scope phase 15 release candidate`) on `dev`, before
creating `feat/release-candidate`.

| Interpreter | Tier | Command | Measured result |
| --- | --- | --- | --- |
| Python 3.14.6 | DuckDB/default | `./run.sh uv run pytest -q` | `351 passed, 7 deselected in 4.47s` |
| Python 3.14.6 | Spark-selected | `./run.sh uv run pytest -q -m spark` | `7 passed, 351 deselected in 8.75s` |
| Python 3.12.13 | DuckDB/default | `./run.sh uv run --python 3.12 pytest -q --no-cov` | `351 passed, 7 deselected in 3.11s` |
| Python 3.12.13 | Spark-selected | `./run.sh uv run --python 3.12 pytest -q -m spark --no-cov` | `7 skipped, 351 deselected in 0.18s` |

The Python 3.12 Spark-selected tier was skipped on this host rather than passing. This is a
measured host capability limitation, not a release-candidate assertion; CI's Spark jobs provision
Java and remain an explicit verification target. After the Python 3.12 measurements, the shared
environment was restored with `./run.sh uv sync --all-extras --dev --python 3.14`.

## Files modified

- `docs/agent_conversations/2026-08-01_release-candidate.md`

## Tests added

- None in this baseline-only task.

## Design decisions

- Preserve skipped Spark results as measured limitations rather than presenting them as passing
  verification.

## Results

- The default suite passed on Python 3.12 and Python 3.14 before implementation began.
- The Spark-selected suite passed on Python 3.14 before implementation began.

