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

## Residue sweep

After removing the runtime, `grep -rn -E 'streamlit|streamlit_ace|AppTest'
src/ tests/ pyproject.toml .github/` produced no matches. Historical mentions remain only under
`docs/plans/`, `docs/review/`, and older session logs; they are durable audit records and are not
runtime code. The README wording is updated separately in Task 11.

## Final implementation results

- The native Qt entry point now serves `wherewolf`, `wherewolf-desktop`, and
  `python -m wherewolf`.
- Removed Streamlit UI modules, configuration, AppTest coverage, the cache factory, byte-based
  exporter, obsolete browser screenshot script, and the Streamlit, Streamlit Ace, and Playwright
  dependencies.
- Retained and adapted shared history, model, Excel, and import-boundary tests rather than
  deleting them because they once mentioned the old UI.
- Added a Help → About notice covering GPL-3.0-only and the preserved pre-0.6 MIT text.
- CI now uses the lockfile explicitly in the lint, DuckDB, and Spark install contracts. Measured
  locally: lint synced the Spark extra and passed ruff/ty; DuckDB-only Python 3.12 synced without
  PySpark; Spark Python 3.12 synced with PySpark available.
- Manual release gates remain: no browser/server, native multi-file dialog, real-window and
  clipboard behavior, query responsiveness, Windows/macOS coverage, and Spark full export.

## Review round 02 — parity-audit correction

- Rechecked every audit mapping identified by `streamlit-parity-and-removal-review-01.md` against
  its collected test node. The audit now uses `PARTIAL` with the untested remainder and `MANUAL`
  for real-window geometry, legal-notice accuracy, and final package-artifact inspection instead
  of treating adjacent tests as proof.
- Added an explicit, visible `Sorted preview only.` disclosure whenever the result grid has a
  local sort, plus `Copy All Visible Column Names` in the header menu.
- Added focused regression assertions for JOIN completion, dialect completion, case-insensitive
  alias rename, keyboard copy, truncation visibility, message categories, exact executable
  translation, and unloaded-schema completion.
- Collected-node verification recorded all new/repaired node IDs. The 3.14 default suite measured
  `350 passed, 7 deselected`; full gates are recorded in the review-round commit.

## Review round 02 verification

- Mutation evidence: changing the sorted-preview disclosure, disabling JOIN table completion, and
  making alias uniqueness case-sensitive each produced a failing cited regression test; each
  mutation was reverted before validation.
- Collected all 65 cited node IDs across the default and Spark-selected collections; no cited node
  is phantom. Parameterized test bases are valid pytest selectors and were checked against their
  collected parameterized children.
- CI install contract remains explicit: lint synchronizes all extras/dev dependencies for `ruff`
  and `ty`; DuckDB tests synchronize dev dependencies without requiring Spark; Spark tests use
  the `spark` extra plus Java in CI. Local quality gates and the default Python 3.12 suite passed;
  the shared environment was restored to Python 3.14 with all extras and dev dependencies.
