# Implementation Plan: Restore Python 3.12 Support

## Problem Definition
Python 3.12 support was previously deprecated due to native segfault ("crash B") issues on CI. That underlying bug in `MainWindow.closeEvent` / `SchemaWorker` has been root-caused and fixed on `dev`. CI probe results confirmed 0 crashes in 30 runs on Python 3.12. The maintainer decided to restore Python 3.12 support as the minimum Python floor while keeping Python 3.14 fully supported.

## Architecture Overview
Restoring Python 3.12 requires:
1. Updating `requires-python` in `pyproject.toml` from `>=3.14` to `>=3.12`.
2. Running `ruff check . --fix` and `ruff format .` to re-parenthesize PEP 758 exception syntax (unparenthesized tuple exception syntax in 3.14) back to 3.12-compatible syntax `except (ErrorA, ErrorB):`.
3. Resolving any remaining syntax or typing constructs ruff demands under Python 3.12 target.
4. Restoring Python 3.12 to the CI matrix in `.github/workflows/ci.yml` alongside Python 3.14, maintaining the `Verify interpreter` step and `--python ${{ matrix.python-version }}` flags.
5. Re-locking dependencies (`uv lock`, `uv sync --all-extras --dev`).
6. Updating `README.md` to state Python 3.12+ requirement and bumping `cacheBuster` query params on image/badge URLs (from `cacheBuster=14` to `cacheBuster=15`).
7. Verifying via quality gates, running `pytest` under both Python 3.12 and 3.14 interpreters, and running `check_flake.sh 25` on 3.14.

## Core Data Structures
No schema or data structure changes are required for this restore task.

## Public Interfaces
- `pyproject.toml`: `requires-python = ">=3.12"`
- `README.md`: Ensure Python requirement states `3.12+`.

## Dependency Requirements
- Python `>=3.12` floor.
- `uv lock` update for lockfile consistency across 3.12 and 3.14.

## Testing Strategy
1. Verify no PEP 758 syntax remains under `src/` (`grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/`).
2. Run `./run.sh uv run ruff check .` and `./run.sh uv run ruff format --check .`.
3. Run quality gates: `scripts/orchestration/run-quality-gates`.
4. Run full pytest suite on Python 3.12: `./run.sh uv run --python 3.12 pytest -q --no-cov`.
5. Run full pytest suite on Python 3.14: `./run.sh uv run --python 3.14 pytest -q --no-cov`.
6. Run `scripts/check_flake.sh 25` on Python 3.14.
