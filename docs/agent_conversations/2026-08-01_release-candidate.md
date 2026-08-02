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

## Final implementation results

- Added artifact-level packaging checks, a clean installed-wheel smoke script, Linux build CI,
  and an offscreen Qt smoke matrix for Ubuntu, macOS, and Windows.
- Rewrote the user documentation for the native desktop workflow; added 0.5.x migration notes,
  the unreleased 0.6.0 changelog, and the maintainer-owned manual acceptance checklist.
- Reviewed and corrected the tag-triggered release workflow to honor the Python 3.12 floor and
  current 3.12/3.14 matrix, provision Linux Qt libraries, smoke a clean installed wheel, and build
  the uploaded release artifacts. No tag was triggered.
- The checked artifact version remains `0.5.2` because the plan explicitly reserves the 0.6.0
  version bump for the maintainer.

## Final verification

| Interpreter | Tier | Command | Measured result |
| --- | --- | --- | --- |
| Python 3.14.6 | DuckDB/default | `./run.sh uv run pytest -q` | `354 passed, 7 deselected in 6.85s` |
| Python 3.14.6 | Spark-selected | `./run.sh uv run pytest -q -m spark` | `7 passed, 354 deselected in 9.55s` |
| Python 3.12.13 | DuckDB/default | `./run.sh uv run --python 3.12 pytest -q --no-cov` | `354 passed, 7 deselected in 5.48s` |
| Python 3.12.13 | Spark-selected | `./run.sh uv run --python 3.12 pytest -q -m spark --no-cov` | `7 skipped, 354 deselected in 0.20s` |

After the Python 3.12 runs, the shared environment was restored with
`./run.sh uv sync --all-extras --dev --python 3.14`.

Artifact inspection used `/tmp/wherewolf/release-artifacts.4zpYXe`:

- `wherewolf-0.5.2-py3-none-any.whl` contains
  `wherewolf-0.5.2.dist-info/licenses/LICENSE` and
  `wherewolf-0.5.2.dist-info/licenses/LICENSES/MIT-pre-0.6.txt`.
- `wherewolf-0.5.2.tar.gz` contains `LICENSE` and `LICENSES/MIT-pre-0.6.txt`.
- The clean installed-wheel smoke run created
  `/tmp/wherewolf/installed-wheel-6je__69_/venv`, installed only default dependencies (no
  PySpark), constructed `MainWindow` with `QT_QPA_PLATFORM=offscreen`, and passed.
- `tests/test_ci_workflow.py` passed, auditing the separate lint, DuckDB, Spark, build, and Qt
  smoke install contracts without matching fragile complete command strings.
- The new Ubuntu/macOS/Windows Qt matrix has not been run remotely in this round. It is recorded
  as **not measured**, not as cross-platform acceptance coverage.

## Maintainer gate remaining

The release candidate is not a release. The maintainer must execute and sign the unchecked
items in `docs/review/manual-acceptance-checklist.md`, obtain actual macOS/Windows Qt job
outcomes, decide the version bump to 0.6.0, and then separately decide whether to promote, tag,
and publish. This session did none of those actions.
