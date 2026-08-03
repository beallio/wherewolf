# Phase 9 — PyQt6 Result Grid

Slug: `pyqt6-result-grid`
Base branch: `dev`
Target release: 0.6.0 (minor). **Do not bump the version in this phase.**

## Context

Phase 8 delivered execution: a query runs off the GUI thread and a `QueryResult` arrives on
the GUI thread carrying a `polars.DataFrame`. It is currently rendered by
`self._results_text.setPlainText(str(result.frame))` — a `QTextEdit` placeholder
(`main_window.py:251`). This phase replaces that with a real grid.

Goal, from the migration document: **meet or exceed the useful `st.dataframe` interactions.**

### What already exists — use it, do not rebuild it

- **`domain/models.py`** — `QueryResult.frame: pl.DataFrame | None`, already validated:
  a succeeded result always has a frame, failed and cancelled never do. **Use as-is.**
- **`desktop/models/catalog_model.py`** — a working `QAbstractTableModel` in this codebase.
  **Read it first.** It establishes the conventions for `rowCount`/`columnCount`/`data`/
  `headerData` signatures and role handling that `ty` accepts here.
- **`desktop/query_controller.py`** — emits `result_ready(QueryResult, ExecutionRequest)` on
  the GUI thread. The grid is populated from that slot. **Do not** reach into the worker.
- **`desktop/widgets/sql_editor.py`** — `SqlEditor` for the "insert header into editor"
  action. It has an existing API; read it rather than guessing.
- **`services/statement_service.py`**, **`services/formatting_service.py`** — untouched here.
- **polars >= 1.41.2** is the dataframe library. Use its typed accessors; do **not** convert
  the whole frame to Python lists to sort it.

### Known defects you must NOT fix here

- `execution/spark_engine.py` swallows exceptions in `get_schema`. Phase 13.
- History is still v1. Phase 11.
- `ui/results.py` is the **Streamlit** results renderer. It is not yours. Deleting Streamlit
  is Phase 14.

### Phase 8 follow-ups folded into this phase

These were deliberately deferred from Phase 8 because they sit in `MainWindow.closeEvent`,
a path that had just been certified crash-free over 75 runs and was not worth destabilising
for cosmetics. Task 12 picks them up:

1. `closeEvent` reaches into `self.query_controller._workers`, a private attribute. Give
   `QueryController` a `shutdown()` method that quits and waits for its own workers.
2. `if hasattr(self, "query_controller") and self.query_controller is not None:` is dead —
   `query_controller` is assigned unconditionally in `__init__`. Remove both halves.
3. `tests/test_catalog_dock.py` repeats
   `qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))`
   eleven times. Express it once as an autouse fixture.

**When you change `closeEvent`, V8 is not optional.** That code path is load-bearing against a
native segfault; see the warning below.

### The crash history you must respect

Phase 8 root-caused a native segfault: `SchemaWorker` QThreads destroyed while running, with
posted events later delivered into freed memory
(`QCoreApplicationPrivate::sendPostedEvents` → `notify_helper`). Measured pre-fix 6/100,
post-fix 0/75; removing the drain reproduces a SIGSEGV on demand.

This phase adds a large widget with selection models, proxy models and context menus — all
QObject-heavy. **Any QObject you parent to a transient window, and any thread you start, must
not outlive its parent.** V8 exists to catch a regression here and it is a hard gate.

`timid = true` in `pyproject.toml` is load-bearing on 3.14. **Do not remove it.**

### Python floor: 3.12, not 3.14

`requires-python = ">=3.12"` was **restored** immediately before this phase, after the segfault
that caused the 3.12 deprecation was root-caused and fixed (see
`docs/review/crash-b-probe-finding.md`). CI tests **both** `3.12` and `3.14`.

Everything you write must run on **Python 3.12**:

- **No PEP 758 unparenthesized `except`.** `except OSError, ValueError:` is a SyntaxError on
  3.12. Write `except (OSError, ValueError):`.
- No 3.13+/3.14-only typing constructs or stdlib APIs.
- `ruff` targets the declared floor, so `ruff check --fix` and `ruff format` will keep you
  honest automatically — **let the tools drive rather than hand-writing modern syntax.**

**Verify on both interpreters before marking a round complete** (see V1). A 3.14-only construct
will pass every local check and then fail the 3.12 CI leg.

Practical warning: `./run.sh uv run --python 3.12 ...` re-syncs the **shared**
`UV_PROJECT_ENVIRONMENT` at `/tmp/wherewolf/.venv` to 3.12. After testing the 3.12 leg, run
`./run.sh uv sync --all-extras --dev --python 3.14` to restore the dev interpreter, or your
subsequent runs silently measure the wrong thing.

### Hard constraint: Streamlit must keep working

`wherewolf` (Streamlit) and `wherewolf-desktop` (Qt) both ship until Phase 14. Do not modify
`src/wherewolf/app.py`, `engines.py`, `ui/`, `export/`, `storage/`, `constants.py` or
`.streamlit/`. Formatting-only churn from `ruff format` is acceptable; behavioural change is
not.

### Repo mechanics that will fail your commits

- `scripts/check_tdd.sh` requires a **flat** `tests/test_<basename>.py` for each staged
  `src/**/*.py`. A new `src/wherewolf/desktop/models/polars_table_model.py` needs
  `tests/test_polars_table_model.py` — not a nested path.
- The pre-commit hook runs `ruff check`, `ruff format`, `ty check`, `pytest` and
  `check_tdd.sh`, and it does `git add -u`, so it sweeps modified tracked files into your
  commit. Stage deliberately.
- Caches live under `/tmp/wherewolf` (a symlink to `~/.local/state/wherewolf-cache`). Run
  project commands through `./run.sh`.
- Commit messages must NOT contain `Co-Authored-By:` or `Claude-Session:` trailers.

### Baseline

`dev` @ `4747e53`: **254 passed, 1 skipped**; ruff/ty clean; CI green on `lint` and
`test (3.14)`. Record your own baseline in Task 1 before changing anything.

## Orchestration Contract

**Slug:** `pyqt6-result-grid`

**Plan file:**

```text
docs/plans/2026-08-01_pyqt6-result-grid.md
```

**Implementation branch:**

```text
feat/pyqt6-result-grid
```

**Round-complete marker:**

```text
/tmp/wherewolf/pyqt6-result-grid_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/pyqt6-result-grid_finalized
```

**Review notes:**

```text
docs/review/pyqt6-result-grid-review-*.md
```

Each review note ends with exactly one status trailer:

```text
STATUS: CHANGES_REQUESTED
```

or:

```text
STATUS: APPROVED
```

---

## Required Agent Protocol

1. Use the **implementer** skill.
2. Work from the repository root.
3. Branch from `dev`.
4. Commit this plan as the first commit on the implementation branch.
5. Follow TDD where behavior changes are testable.
6. Run quality gates before marking any round complete.
7. Do not write your own review.
8. Do not create files under `docs/review/`.
9. Do not delete files under `docs/review/`.
10. Review notes are durable audit records and must be committed.
11. Resolving a review note means:
    - implement the requested changes;
    - run quality gates;
    - commit the code/docs changes;
    - commit the review note itself if it is not already committed;
    - recreate the round-complete marker.
12. After finalization, stop polling and exit cleanly.

---

## Setup

Start from `dev`:

```bash
git checkout dev
# ORCH_LOCAL_ONLY: local trial branch, skipping origin pull
git checkout -b feat/pyqt6-result-grid
```

Commit this plan first:

```bash
git add docs/plans/2026-08-01_pyqt6-result-grid.md
git commit -m "docs(plan): add pyqt6-result-grid implementation plan"
```

---

## Implementation Tasks

Each task is one commit, Red before Green. Tasks 2–5 are **Qt-model-only or pure functions** —
no widgets — so most of the logic lands testable without a GUI.

### Task 1 — Session log and baseline
Create `docs/agent_conversations/2026-08-01_pyqt6-result-grid.md`. Record the baseline commit
and the measured `pytest -q` tally. No source changes.
Commit: `docs: record result grid baseline`.

### Task 2 — `PolarsTableModel`: read-only frame view
**Red** (`tests/test_polars_table_model.py`): row/column counts match the frame; `DisplayRole`
renders values; column headers come from `frame.columns`; an empty frame yields 0 rows and 0
columns without raising; a frame with 0 rows but real columns still reports its columns.
**Green**: `src/wherewolf/desktop/models/polars_table_model.py`, subclassing
`QAbstractTableModel`. Follow `catalog_model.py`'s signature conventions.
Commit: `feat(desktop): add polars-backed result table model`.

### Task 3 — Display vs raw values, and nulls
**Red**: `Qt.ItemDataRole.UserRole` returns the **typed** Python value (int stays int, date
stays date); `DisplayRole` returns a string; nulls render as a distinguishable placeholder and
are **not** the string `"None"`; a null is distinguishable from the literal string `"null"` in
a text column.
**Green**: add the roles. Do not stringify the whole frame.
Commit: `feat(desktop): expose typed values and null rendering in the table model`.

### Task 4 — `TypedSortProxyModel`: sorting that respects type
**Red** (`tests/test_typed_sort_proxy_model.py`): numeric columns sort numerically —
`[2, 10, 1]` must sort `[1, 2, 10]`, **not** `[1, 10, 2]` (this is the defect this task
exists to prevent); dates sort chronologically; strings sort lexicographically; **null
ordering is defined and asserted** (state the rule — nulls last on ascending — and test both
directions); a third sort click **restores the original row order**.
**Green**: `TypedSortProxyModel` sorting on the `UserRole` typed value.
Commit: `feat(desktop): add type-aware sort proxy for result grid`.

### Task 5 — Clipboard serializers (pure functions, no Qt widgets)
**Red** (`tests/test_clipboard_serializers.py`): TSV of a contiguous range; with and without
column names; **visual column order is honoured** when columns have been moved; a quoted
header variant; **discontiguous selection** serialises deterministically (state the rule);
values containing tabs or newlines are handled per a stated rule.
**Green**: `src/wherewolf/desktop/clipboard_serializers.py` — plain functions over
`(frame, selected_cells, column_order, options)`. Keep them Qt-free so they are testable
without a GUI.
Commit: `feat(desktop): add result grid clipboard serializers`.

### Task 6 — `ResultTableView`: selection and copy
**Red** (`tests/test_result_table_view.py`, `qtbot`): cell, range, row and column selection;
`Ctrl+C` places the expected TSV on the clipboard; copy respects the current sort order as
displayed.
**Green**: `src/wherewolf/desktop/widgets/result_table_view.py`. Parent it properly; do not
leave QObjects owned by nothing.
Commit: `feat(desktop): add result table view with selection and copy`.

### Task 7 — Header context menu
**Red**: sort ascending → descending → clear cycles and the indicator reflects it; copy header
name; copy quoted header; insert header into the editor at the cursor.
**Green**: header context menu wired to Task 4 and Task 5.
Commit: `feat(desktop): add result grid header context menu`.

### Task 8 — Body context menu
**Red**: copy, copy with column names, copy quoted header — each produces exactly what the
Task 5 serializers specify.
**Green**: body context menu.
Commit: `feat(desktop): add result grid body context menu`.

### Task 9 — Column operations
**Red**: move, hide, show, auto-size, reset-to-default; a hidden column is excluded from copy;
reset restores both order and visibility.
**Green**: column operations on the view.
Commit: `feat(desktop): add result grid column operations`.

### Task 10 — Preview search/filter
**Red**: filtering narrows visible rows; **filtered row indices map back to the correct source
rows** (assert a value, not just a count); clearing the filter restores all rows; filter
combines correctly with an active sort.
**Green**: filter over the proxy.
Commit: `feat(desktop): add result grid search and filter`.

### Task 11 — Wire into `MainWindow`
**Red** (`tests/test_main_window.py`): a succeeded `QueryResult` populates the grid with the
frame's real values; a failed result shows the error and leaves no stale rows; a cancelled
result clears the grid; the status bar reports row count and truncation.
**Green**: replace the `QTextEdit` placeholder (`main_window.py:251`). Keep the failed and
cancelled message paths that Phase 8 established.
Commit: `feat(desktop): render query results in the result grid`.

### Task 12 — Phase 8 follow-ups
**Red**: a test asserting `QueryController.shutdown()` quits and waits for its workers, and
that `MainWindow.closeEvent` no longer touches `_workers` directly.
**Green**: add `QueryController.shutdown()`; call it from `closeEvent`; delete the `hasattr`
guard; replace the eleven repeated `waitUntil` lines in `tests/test_catalog_dock.py` with one
autouse fixture.
**Then run V8 immediately** — this task edits the teardown path.
Commit: `refactor(desktop): encapsulate worker shutdown and drop dead guards`.

### Task 13 — README and close out
Document the grid's interactions. Bump the README image `cacheBuster` per AGENTS.md §13.
Finalise the session log with **measured** results.
Commit: `docs: document result grid and close out session log`.

## Quality Gates

Run before marking any round complete:

```bash
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

The round is not complete unless:

1. all requested implementation work is done;
2. all relevant tests pass;
3. build/typecheck gates pass;
4. review notes have not been deleted;
5. the working tree is clean;
6. all code/docs changes are committed.

---

## Verification

State sample sizes and decision rules **before** measuring. Record measured outcomes, not
"green".

### V1 — Suite and gates, on BOTH interpreters
```bash
./run.sh uv run pytest -q                        # 3.14 — record the tally
scripts/orchestration/run-quality-gates          # must exit 0

./run.sh uv run --python 3.12 pytest -q --no-cov # 3.12 — record the tally
./run.sh uv sync --all-extras --dev --python 3.14 # restore the dev interpreter
```
Record **both** tallies. **Failure looks like:** running only 3.14 and discovering a
3.14-only construct when CI runs the 3.12 leg. A SyntaxError on 3.12 does not fail
gracefully — the suite cannot even import.

### V2 — Streamlit path behaviourally untouched
```bash
git diff dev..HEAD -- src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/storage/ src/wherewolf/constants.py .streamlit/
```
Formatting-only churn is acceptable; behavioural change is not. Then:
```bash
./run.sh uv run pytest -q --no-cov tests/test_app.py tests/test_app_flow.py \
  tests/test_app_cancel.py tests/test_engines.py tests/test_duckdb_engine.py
```

### V3 — A real frame really renders
The end-to-end test must assert **actual cell values and column names**, not that "a model
exists". **Failure looks like:** a test asserting only `rowCount() > 0`.

### V4 — Sorting is typed, not lexicographic
```bash
./run.sh uv run pytest -q --no-cov tests/test_typed_sort_proxy_model.py -v
```
Must include the `[2, 10, 1] -> [1, 2, 10]` case. **Failure looks like:** `[1, 10, 2]`
accepted, or null ordering left unasserted.

### V5 — Clipboard output is exact
Assert exact strings, including separators and line endings. **Failure looks like:** a test
asserting only that the clipboard is non-empty.

### V6 — No model mutation off the GUI thread
Assert the model is populated from the `result_ready` slot on the GUI thread and that no
worker touches it. **Failure looks like:** the model being handed to a QThread.

### V7 — Mutation checks: prove the new tests bite
**Commit first.** Verify each mutation applied (`git diff --quiet` must be **false**) before
trusting a "no bite", and grep with `--color=no`. Both mistakes have produced false findings
in this project.

1. Sort on the display string instead of the typed value → the `[2, 10, 1]` test must FAIL.
2. Reverse the null-ordering rule → the null-ordering test must FAIL.
3. Copy in model order instead of visual column order → the column-order test must FAIL.
4. Include hidden columns in copy → the hidden-column test must FAIL.
5. Off-by-one in the filtered→source row mapping → the mapping test must FAIL.
6. Drop the third-click sort reset → the restore-original-order test must FAIL.

Record the failing node id for each, revert between each, and confirm `git status --short`
prints nothing.

### V8 — No native crash regression (hard gate)
```bash
scripts/check_flake.sh 25    # run TWICE; 50 runs total
```
**Pass:** 0 native crashes in 50. **Failure:** any crash, or exit 2.

Two things learned the hard way in Phase 8:
- `check_flake.sh` overwrites `/tmp/wherewolf/flake-guard-last.txt` every run, so a crash's
  trace is destroyed by the next iteration. **Preserve per-run logs** or you will report a
  count with no evidence.
- A single clean batch of 25 proves very little: at a 6% rate, `0/25` happens ~21% of the time
  for code that still crashes. That is why this asks for 50 and why you must state the number.

If a crash appears: capture the trace, count the progress marks before
`Fatal Python error`, and map that to `pytest --collect-only -q` to locate it. Note that
`sendPostedEvents` crashes are **delayed** — the crash site names the test that pumped the
event loop, not the one that leaked the object.

### V9 — Teardown still safe after Task 12
Re-run V8 after Task 12 specifically, and say so. Changing `closeEvent` invalidates any
earlier measurement.

### Deferred and explicitly NOT verified
- **No human has seen the grid.** All Qt tests are offscreen. Say so.
- **No performance measurement.** Do not imply the migration document's responsiveness targets
  were met. If you render a large frame, say how large and that it was not benchmarked.
- Export is Phase 12; history v2 is Phase 11; Spark is Phase 13.
- macOS and Windows unverified.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not modify the Streamlit path or `DuckDBEngine`. Do not touch `main`. Do not bump the package
version — 0.6.0 belongs to the final cutover.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished pyqt6-result-grid
```

This writes:

```text
/tmp/wherewolf/pyqt6-result-grid_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer pyqt6-result-grid`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/pyqt6-result-grid-review-*.md
```

When a review note exists or a new review note appears:

1. Read the full review note.
2. If the note ends with:

   ```text
   STATUS: CHANGES_REQUESTED
   ```

   then resume work.

3. Clear the round-complete marker:

   ```bash
   scripts/orchestration/clear-finished pyqt6-result-grid
   ```

4. Address every requested change.
5. Run quality gates:

   ```bash
   scripts/orchestration/run-quality-gates
   scripts/orchestration/check-review-notes-not-deleted
   ```

6. Commit code/docs fixes.
7. Commit the review-note file itself if it is not already committed:

   ```bash
   git add docs/review/pyqt6-result-grid-review-*.md
   git commit -m "docs(review): record pyqt6-result-grid review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished pyqt6-result-grid
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer pyqt6-result-grid` after the next review note is created.

---

## Approval Handling

If the latest review note ends with:

```text
STATUS: APPROVED
```

then:

1. Confirm every previous review item has been addressed.
2. Confirm all review notes are committed:

   ```bash
   scripts/orchestration/check-review-notes-committed pyqt6-result-grid
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize pyqt6-result-grid
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/pyqt6-result-grid_finalized
   ```

6. Stop polling and exit cleanly.

---

## Review Rules

Do not write your own review.

Do not create files under:

```text
docs/review/
```

Do not delete files under:

```text
docs/review/
```

Only the orchestrator writes review notes. Your job is to read them, resolve them, commit them as audit records, and continue the loop.

---

## Finalization Rules

Only finalize after a review note with:

```text
STATUS: APPROVED
```

Finalization is performed with:

```bash
scripts/orchestration/finalize pyqt6-result-grid
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/pyqt6-result-grid_finished
/tmp/wherewolf/pyqt6-result-grid_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
