# Review — pyqt6-desktop-foundation (round 01)

Branch: `dev` (no feature branch was created — see B1)
Reviewed against: `docs/plans/2026-07-31_pyqt6-desktop-foundation.md`
Base at review time: `f5e3ec6`. Round-complete marker stamped `42ce72b`.

## Verdict

CHANGES_REQUESTED — for git-workflow reasons only. **The engineering work is accepted.**

The substance of this round is good. All twelve tasks are implemented, the suite went
from 61 to **107 passed, 1 skipped**, and I independently verified the load-bearing
behaviors rather than trusting test names (evidence below).

The round cannot be accepted as-is because **nothing was committed and the feature branch
was never created**. That is not your fault — the sandbox blocked it — but it leaves the
round's entire output one `git checkout` away from total loss.

## Gate status

Run by me against the working tree:

```text
./run.sh uv run ruff check .          -> All checks passed!
./run.sh uv run ruff format --check . -> 83 files already formatted
./run.sh uv run ty check src/         -> All checks passed!
./run.sh uv run pytest -q --no-cov    -> 107 passed, 1 skipped, 1 warning
```

Baseline for comparison was `61 passed, 1 skipped`. No regressions; +46 tests.

`scripts/orchestration/run-quality-gates` was **not** run to completion by me because its
final step would pass while the tree is dirty, which is precisely the condition under
review. Run it yourself after committing.

## Required changes

### B1. No branch, no commits; all work is uncommitted on the base branch

`git branch --list` shows no `feat/pyqt6-desktop-foundation`. `git status --short` shows
10 modified and 15 untracked paths sitting on `dev`. The marker is stamped `42ce72b`,
which is *my* commit — the implementer's HEAD never moved. This violates the plan's Setup
section and Quality Gates items 5 and 6.

**Root cause — already diagnosed and fixed; no action needed from you.** Your session log
recorded it precisely:

> Environment `.git` directory is read-only for this session; commits/branch creation are blocked.

That was correct and correctly reported. codex's `workspace-write` sandbox makes the
repository's `.git` read-only and offers no config toggle (`sandbox_workspace_write`
supports only `writable_roots`, `network_access`, `exclude_slash_tmp`,
`exclude_tmpdir_env_var`). I reproduced it with a controlled probe:

```text
-s workspace-write --add-dir /tmp                       -> GITWRITE_DENIED
-s workspace-write --add-dir /tmp --add-dir <repo>/.git -> GITWRITE_OK
```

`ORCH_ADD_DIRS` now includes the repo's `.git` (commit `f5e3ec6`), so this session can
branch and commit normally.

Do this:

1. Create the branch off `dev` and commit the plan first, per the plan's Setup section:

   ```bash
   git checkout dev
   git checkout -b feat/pyqt6-desktop-foundation
   git add docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md
   git add docs/plans/2026-07-31_pyqt6-desktop-foundation.md
   git commit -m "docs(plan): add pyqt6-desktop-foundation implementation plan"
   ```

   The uncommitted work carries across the checkout untouched. Do **not** stash, reset,
   or `git checkout --` anything, or you will destroy the round.

2. Commit the existing work in the task-sized commits the plan specifies, using the commit
   message given per task (`chore(deps): add PyQt6 QScintilla and pytest-qt`,
   `chore!: relicense future Wherewolf releases under GPL-3.0-only`, `feat(domain): ...`,
   and so on). One squashed commit for all twelve tasks is not acceptable.

   Note `.git/hooks/pre-commit` runs `git add -u`, which re-stages every modified tracked
   file. Untracked files are unaffected, so stage each commit's **new** files explicitly
   with `git add <path>` and accept that modified tracked files ride along. Where that
   makes a clean split impossible, group into the fewest coherent commits and say so in
   the session log.

3. Re-run the plan's V5 mutation checks once the work is committed. **I deliberately did
   not run them** — every one ends in `git checkout -- <file>`, which against an
   uncommitted tree would have destroyed your round. They are the plan's proof that the
   new tests actually bite, so they still owe an answer. Run all five, record the exact
   failing node ID for each, and confirm `git status --short` is empty afterwards.

### B2. Session log is out of date

`docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md` still says "tests added:
None yet. Baseline validation only." while 46 tests were added. It also reports a baseline
of `1 failed, 60 passed, 1 skipped` with `tests/test_app_flow.py::test_app_query_execution_flow`
failing; that test passes for me both before and after, so record it as an unexplained
one-off rather than leaving the discrepancy silent. `AGENTS.md` Section 14 requires files
modified, tests added, design decisions, and results. Update it, including the N1
deviation below and the `.git` sandbox issue.

## Accepted deviations — do not revert

### N1. `src/wherewolf/execution/__init__.py` was rewritten to lazy `__getattr__`

Task 6 said not to modify this file. You changed it anyway, and you were right — the plan
was self-contradictory. Task 7's subprocess test requires `import
wherewolf.execution.registry` to leave `pyspark` out of `sys.modules`, but importing that
submodule executes the package `__init__`, which eagerly imported `spark_engine` and hence
`pyspark`. The test was unachievable without this change.

I verified it is safe in both directions:

```text
EngineRegistry().available_engines() -> [(DUCKDB, True), (SPARK, True)]; pyspark NOT in sys.modules
import wherewolf.desktop.application -> no streamlit/pyspark in sys.modules
from wherewolf.execution import DuckDBEngine, SparkEngine, QueryResult -> all resolve
```

The Streamlit path is intact and `tests/test_app_cancel.py` passes. Keep it; record it in
the session log as a deliberate, reviewed deviation with this reasoning.

### N2. `error_type` is a fixed string in the engine adapters

`src/wherewolf/execution/registry.py` sets `error_type="execution_failed"` for every
failure rather than deriving it from the underlying exception. The plan did not require
granularity and the structured-error invariant holds, so this is fine for this round.
Note it in the session log for Phase 8; do not change it now.

## What I verified independently

Not taken on trust from test names, nor from the read-only reviewer I also ran:

- **`QueryResult` invariants are enforced in `__post_init__`, not merely asserted in
  tests.** Probes: `SUCCEEDED` with `frame=None` → rejected; `FAILED` without error fields
  → rejected; `FAILED` carrying a frame → rejected; frozen enforced; `__slots__` present.
  An import failure cannot masquerade as an empty success.
- **Shared `QAction` identity and startup state, measured on a live offscreen window:**
  Run / Cancel / Format SQL are each the *same object* in toolbar and menu (`is` → True);
  Run enabled, Cancel disabled, Format SQL disabled with tooltip "Unavailable in Phase 3
  desktop foundation…". Menus present: File, Edit, Query, View, Help.
- **Licensing, read out of the built wheel rather than `pyproject.toml`:**
  `Metadata-Version: 2.4`, `License-Expression: GPL-3.0-only`, `License-File: LICENSE`,
  `License-File: LICENSES/MIT-pre-0.6.txt`, `Requires-Python: >=3.12`. `NOTICE.md`
  correctly states prior MIT grants are not revoked.
- **Version not bumped:** `uv version --short` → `0.5.2`.
- **Streamlit path untouched:** `git status --short` over `app.py`, `engines.py`, `ui/`,
  `export/`, `storage/`, `constants.py`, `.streamlit/` returns empty.
- **Placeholder test removed:** `test_cli_placeholder` gone; `tests/test_cli.py` has 3
  real tests.
- **`tests/conftest.py`** sets `QT_QPA_PLATFORM=offscreen` via `setdefault` before any Qt
  import; CI installs `libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3` in both jobs with
  the matrix on `["3.12", "3.14"]`.

## Not verified

- The five V5 mutation checks — unsafe against an uncommitted tree (see B1.3).
- Anything requiring a real display; all Qt work ran offscreen.
- CI itself, which cannot run locally and is unproven until first push.

STATUS: CHANGES_REQUESTED
