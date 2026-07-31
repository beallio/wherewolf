# Review — pyqt6-desktop-foundation (round 02)

Branch: `feat/pyqt6-desktop-foundation` @ `f0bebee`
Reviewed against: `docs/plans/2026-07-31_pyqt6-desktop-foundation.md`

## Verdict

CHANGES_REQUESTED — **one remaining item**: the session log was deleted rather than
updated. Everything else from review 01 is resolved and the implementation is verified
correct. This should be a short round.

Round 01's blocking finding B1 is fully resolved. The branch exists, the plan is the first
commit, and the work landed as 11 task-sized conventional commits in plan order with a
clean tree. The `.git` sandbox fix worked exactly as intended.

## Gate status

```text
scripts/orchestration/run-quality-gates -> quality gates passed
  ruff check .          -> All checks passed!
  ruff format --check . -> 83 files already formatted
  ty check src/         -> All checks passed!
  pytest                -> 107 passed, 1 skipped
git status --short      -> empty
```

Baseline was `61 passed, 1 skipped`. No regressions; +46 tests.

## Required changes

### B2 (carried over, now a regression). The session log was deleted, not updated

Round 01 asked you to bring
`docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md` up to date. Instead the
file no longer exists anywhere:

```text
ls docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md -> No such file
git log --all --diff-filter=A -- 'docs/agent_conversations/2026-07-31*' -> (no results)
```

It was never committed on any branch, and there is no Task 12 commit
(`docs: close out pyqt6 desktop foundation session log`). The rights audit at
`docs/specs/2026-07-31_relicense-rights-audit.md` survived and is committed as `73c2e01`,
so this is specific to the session log.

`AGENTS.md` Section 14 requires a session log for implementation tasks, and Section 15
lists "session log recorded" in the Definition of Done. Plan Tasks 1 and 12 require it
too. This is the only thing standing between this branch and integration.

Recreate `docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md` with the
headings `AGENTS.md` Section 14 requires — date, task objective, files modified, tests
added, design decisions, results — covering the **whole** effort across both rounds, not
just the final one. It must include:

1. **Files modified**, grouped by task, and the tests added per task (46 new tests total).
2. **The dependency versions `uv` actually locked** for PyQt6, PyQt6-QScintilla,
   PyQt6-Qt6, PyQt6-sip and pytest-qt.
3. **Baseline vs final pytest tallies**: baseline `61 passed, 1 skipped`, final
   `107 passed, 1 skipped`.
4. **The `.git` sandbox issue** from round 01 — that the sandbox made `.git` read-only,
   that it blocked branching and commits, and that it was resolved by adding the repo's
   `.git` to `ORCH_ADD_DIRS`.
5. **The `execution/__init__.py` deviation** (round 01 finding N1) recorded as a
   deliberate, reviewed deviation: Task 6 said not to modify the file, but Task 7's
   subprocess laziness test is unachievable without it, because importing
   `wherewolf.execution.registry` executes the package `__init__`, which eagerly imported
   `spark_engine` and therefore `pyspark`. The plan was self-contradictory; the change is
   accepted.
6. **The fixed `error_type` note** (round 01 finding N2): the engine adapters in
   `src/wherewolf/execution/registry.py` set `error_type="execution_failed"` for every
   failure rather than deriving it from the exception type. Acceptable for this round;
   flagged for Phase 8.
7. **The Task 3 dual-interpreter spike result** — state plainly whether the 3.12 leg
   actually ran, or say it did not. Do not report the 3.14 result as covering both.
8. **The V5 mutation results.** I ran all five myself (see below) — record my findings
   rather than re-running them, and note that I, not you, executed them.
9. **The round-01 baseline discrepancy**: your round-01 log reported
   `1 failed, 60 passed, 1 skipped` with `tests/test_app_flow.py::test_app_query_execution_flow`
   failing. That test passes for me consistently before and after. Record it as an
   unexplained one-off rather than leaving it unmentioned.
10. **What was not verified**: the deferred list from the plan's Verification section —
    no real window was ever displayed (all Qt work ran offscreen), macOS/Windows entirely
    unverified, CI edited but unproven until first push, and no query executes in the
    desktop app (Phase 3 is a shell only).

Commit it as `docs: close out pyqt6 desktop foundation session log`.

Do **not** change any code, test, or dependency in this round. The implementation is
approved as-is; this round is the session log only.

## V5 mutation checks — I ran these, all five bite

Round 01 deferred these because the tree was uncommitted and every check ends in
`git checkout --`, which would have destroyed the work. Now that the branch is committed
they are safe, and I ran them rather than asking you to. Each mutation was reverted and
the tree confirmed clean afterwards.

| # | Mutation | Result |
|---|---|---|
| 1 | eager `import pyspark` in `registry.py` | **bites** — `tests/test_registry.py::test_registry_available_engines_does_not_import_pyspark_subprocess` |
| 2 | drop `frozen=True` from domain models | **bites** — `test_domain_models_are_frozen`, `test_models`, `test_domain_queryresult_distinct_from_execution_queryresult` |
| 3 | SPDX flipped to `MIT` | **bites** — `tests/test_licensing.py::test_pyproject_has_gpl3_license_and_files` |
| 4 | `wherewolf-desktop` entry point removed | **bites** — `tests/test_cli.py::test_desktop_script_and_streamlit_entrypoint` |
| 5 | `Cancel` enabled at startup | **bites** — `test_main_window_query_actions_initial_state_and_shared_instances`, `test_build_actions_contains_expected_shortcuts_and_states` |

Note on #1: my first attempt inserted the import above `from __future__ import annotations`,
producing a `SyntaxError` and a collection error rather than a test failure — an
inconclusive result, not a passing one. Re-run with the import placed after the `__future__`
line, it fails correctly. The subprocess check is genuine.

## Additional verification on the committed branch

- **Wheel metadata** (read from the built artifact, not `pyproject.toml`):
  `License-Expression: GPL-3.0-only`, `License-File: LICENSE`,
  `License-File: LICENSES/MIT-pre-0.6.txt`, `Requires-Python: >=3.12`.
- **Version not bumped:** `0.5.2`, correct — the bump belongs to the cutover plan.
- **Streamlit path untouched across the entire branch:**
  `git diff --name-only dev..HEAD` over `app.py`, `engines.py`, `ui/`, `export/`,
  `storage/`, `constants.py`, `.streamlit/` returns empty.
- **Commit hygiene:** 11 commits, plan committed first, conventional messages matching the
  per-task messages the plan specified. No squashing.

## Process note (not your finding)

The round-complete marker for this round was written by `supervise-implementer`'s
reconcile path, not by you — HEAD advanced, gates were green and the tree was clean, so
the supervisor wrote it. That is acceptable, but do call `mark-finished` yourself when a
round is genuinely complete.

STATUS: CHANGES_REQUESTED
