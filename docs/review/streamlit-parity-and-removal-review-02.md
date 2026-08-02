# Review — streamlit-parity-and-removal (round 02)

Branch: `feat/streamlit-parity-and-removal` @ `deae042`
Reviewed against: `docs/plans/2026-08-01_streamlit-parity-and-removal.md` and review 01

## Verdict

APPROVED.

The parity audit now holds where it previously did not, and I validated that by mutation across
three subsections rather than by reading it.

## J1 — resolved, and verified three ways

**Every cited node exists.** I extracted all node ids from the audit and diffed them against the
collected set:

```text
cited nodes: 65
cited but NOT collectable: (none)
```

Two rows previously cited tests that did not exist at all. That class of error is now
mechanically excluded — and your log records the same check independently, including that
parameterized bases resolve to their collected children.

**Three mutations bite, each on a row that previously failed:**

| mutation | failing test |
|---|---|
| empty the `Sorted preview only.` label | `test_active_local_sort_discloses_that_only_the_preview_is_sorted` |
| remove the truncation disclosure | `test_main_window_query_result_details_and_metrics` |
| drop Format SQL from the toolbar | `test_main_window_query_actions_initial_state_and_shared_instances` |

Those were three of the worst prior mismappings — a label that did not exist, a test that set
`truncated=False` and never checked, and a criterion citing an unrelated Show Completion test.
All three now fail when the behaviour is broken, which is the only thing that makes a parity
matrix worth having.

**The missing feature is built.** `main_window.py:367` now carries
`QLabel("Sorted preview only.")`, shown whenever the grid has a local sort. That criterion was
recorded as satisfied last round for behaviour that had never been implemented; it exists now
and is asserted.

**`PARTIAL` is used honestly.** Rows where a test covers part of a compound criterion now say so
with the untested remainder named, and real-window geometry, legal-notice accuracy and package
artifact inspection moved to `MANUAL`. That is the correct answer for things offscreen tests
cannot prove.

## Final state — measured by review

| check | result |
|---|---|
| default tier, **3.14** | 351 passed, 7 deselected |
| default tier, **3.12** | 351 passed, 7 deselected — identical |
| **spark tier** | 7 passed, 351 deselected |
| `run-quality-gates` | pass |
| **V10** crash gate 25 + 25 | **0 native crashes / 50** |
| **V4** streamlit residue in `src/`, `tests/`, `pyproject.toml`, `.github/` | none |
| **V3** entry points | `wherewolf` → `cli:main` → `desktop_main()`; `__main__.py` present; `wherewolf-desktop` intact |
| cited-node existence | 65 / 65 collect |
| `ty check .` | All checks passed |
| `git status --short` | clean |

**V6, the check that broke the previous phase:** `lint` installs `--extra spark` (line 32) so
`ty` can resolve pyspark; `test-duckdb` installs `--locked --dev` with **no** extras, which is
what genuinely proves a DuckDB-only install; `test-spark` installs `--extra spark` and runs
`-m spark`. Each leg installs what its own tooling needs. `ty check .` passes locally against the
same configuration.

**V10 is clean at 0/50** — deleting the Streamlit path did not disturb Qt teardown ordering,
which was the specific risk given this project's segfault history.

## What this phase delivered

Streamlit is gone: `app.py`, `engines.py`, `ui/file_browser.py`, `ui/results.py`,
`export/exporter.py`, `.streamlit/`, and the `streamlit`, `streamlit-ace` and `playwright`
dependencies. `wherewolf` and `python -m wherewolf` now open a native Qt window.

Eleven commits in round 01, one per task with deletions separated by target — after that slipped
in two consecutive phases, it landed here, which is the phase where it mattered most.

Round 02 also added real capability while closing gaps: the sorted-preview disclosure,
`Copy All Visible Column Names`, and focused assertions for JOIN completion, dialect completion,
case-insensitive alias rename, keyboard copy, truncation visibility, message categories, and
exact executable translation.

## Minor — no action needed

The session log records `350 passed` where I measure **351**; the last commit
(`deae042`, "verify streamlit removal audit claims") almost certainly landed after that
measurement. Not worth a round.

## The manual gates are now the release gate — this is for the maintainer

These criteria are **`MANUAL` and unverified by any human**. They block 0.6.0, not this merge:

- no browser tab or local web server is started on launch;
- the native multi-file dialog appears where supported;
- real-window geometry, dock and splitter restoration;
- clipboard behaviour against a real desktop clipboard;
- UI responsiveness during a long query;
- Spark full export;
- macOS and Windows behaviour;
- legal-notice accuracy and license files in the built wheel and sdist.

Someone needs to launch the application and click through these before release. Everything above
them in this review is offscreen-verified only.

## Note on the round

Review 01 found that 31 of 62 cited mappings did not hold. Round 02 did not argue with that — it
rechecked every mapping, downgraded what was overstated, built the one missing feature, and added
its own mutation evidence. That is the right response to a hard finding, and the audit is now
worth what it claims.

STATUS: APPROVED
