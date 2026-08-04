# Plan: Desktop shell UI fixes: menus, execution feedback, and shutdown (desktop-shell-ui-fixes)

## Context

A UI audit of `src/wherewolf/desktop/` found six shell-level defects. The app's
threading, error surfacing, and results grid are sound; what is missing is
standard desktop-shell convention and execution feedback. All six are visible to
a user in the first minute of use.

1. **The File menu contains one item — Clear History** (`main_window.py:890-892`).
   There is no Quit action anywhere in the application. `Add Datasets…` is the
   primary entry point and already owns `Ctrl+O` (`actions.py:43-45`) but appears
   only on the toolbar, never in a menu.
2. **No menu mnemonics.** Menus are added as `"File"`, `"Edit"`, `"Query"`,
   `"View"`, `"Help"` with no `&` (`main_window.py:890`, `894`, `931`, `942`,
   `960`), so `Alt+F` does nothing.
3. **No progress feedback during query execution.** Running sets static
   status-bar text and enables Cancel (`main_window.py:441-451`). There is no
   elapsed indicator, so a 200 ms query and a hung 40 s query look identical.
4. **No empty-result state.** A successful query returning zero rows renders an
   empty grid, indistinguishable from "no query run yet"
   (`main_window.py:453-505`). Only an empty-*catalog* banner exists
   (`main_window.py:830`).
5. **Drag-and-drop is not equivalent to Add Datasets.** `CatalogDock.dropEvent`
   calls `CatalogDock.add_paths`, which emits `error_reported` only when the
   report carries warnings (`catalog_dock.py:86`, `102`). It never queues schema
   or profile workers and never reports success. `MainWindow._on_add_datasets`
   does all of that (`main_window.py:589-628`). Two entry points to one action
   behave differently.
6. **Adding a duplicate dataset is silent.** `CatalogService.add_paths` collects
   skipped duplicates into `report.duplicates` (`catalog_service.py:65`), and
   `_on_add_datasets` never reads that field, so nothing is shown.
7. **Quitting can hang indefinitely.** `closeEvent` calls `worker.quit()` then an
   unbounded `worker.wait()` for every schema and profile worker before
   `query_controller.shutdown()` runs (`main_window.py:1056-1067`). `quit()` only
   ends a `QThread`'s event loop; it does not interrupt a `run()` body already
   blocked inside DuckDB. Closing during a long query freezes the window with no
   indication.

Out of scope by explicit decision: session persistence of engine / input dialect /
translation target / last query / Show Hidden Files, and results-grid
virtualization. Catalog persistence is tracked separately in
`feature-ideation-workbench-depth.md` (idea 1) and is not part of this plan.

### Cache-root prerequisite

`orchestration.conf` documents `/tmp/wherewolf` as a symlink to
`~/.local/state/wherewolf-cache`, kept off the quota-limited tmpfs. **That is no
longer true.** `/tmp/wherewolf` is currently a real directory on the tmpfs and
the symlink target does not exist. Every cache path is pinned to
`/tmp/wherewolf`:

- `[tool.uv] cache-dir` and `[tool.ruff] cache-dir` and
  `[tool.pytest.ini_options] cache_dir` and `[tool.coverage.run] data_file` in
  `pyproject.toml`;
- `UV_PROJECT_ENVIRONMENT`, `XDG_CACHE_HOME`, `PYTHONPYCACHEPREFIX`, `TMPDIR` in
  `run.sh`.

The tmpfs enforces a per-user quota whose reboot default is 2387 MiB. The cache
root is already 875 MiB (865 MiB of it the uv cache), and
`scripts/orchestration-hooks/quality-gates` runs the full pytest suite with
coverage on every round. A multi-round implementer run exhausts the quota
mid-flight; this has happened before. Task 0 restores the documented symlink,
which moves all of the above off the tmpfs in one step with no edits to
`pyproject.toml` or `run.sh`, and adds a budget gate the later tasks re-run.

**Slug used throughout this plan:** `desktop-shell-ui-fixes`

---

## Orchestration Contract

**Slug:** `desktop-shell-ui-fixes`

**Plan file:**

```text
docs/plans/2026-08-03_desktop-shell-ui-fixes.md
```

**Implementation branch:**

```text
feat/desktop-shell-ui-fixes
```

**Round-complete marker:**

```text
/tmp/wherewolf/desktop-shell-ui-fixes_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/desktop-shell-ui-fixes_finalized
```

**Review notes:**

```text
docs/review/desktop-shell-ui-fixes-review-*.md
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

## Scope discipline

- Implement only the units the plan lists. Do not modify files outside the plan's scope.
- Do not change runtime behavior beyond what the plan specifies. A `refactor` or
  `cleanup` commit must preserve observable behavior.
- Never edit a test's expected value to make a behavior change pass. If a test
  legitimately must change, that change must be required by the plan or a review
  note, and you must record the rationale in the session log.
- If you spot an unrelated improvement, do not make it here — note it in the
  session log for a separate plan.

---

## Setup

Start from `dev`:

```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/desktop-shell-ui-fixes
```

Commit this plan first:

```bash
git add docs/plans/2026-08-03_desktop-shell-ui-fixes.md
git commit -m "docs(plan): add desktop-shell-ui-fixes implementation plan"
```

---

## Implementation Tasks

Each task below is atomic: one coherent behavior change, its own tests, its own
commit. Do them in order. Do not batch commits. After every task, run the cache
budget gate from Task 0 (`scripts/check_cache_budget.sh`) and record its printed
byte count in the session log.

Follow TDD for tasks 1-7: write the failing test first, run it, record the
failure output, then implement.

Existing tests already assert menu structure and shortcuts —
`tests/test_main_window.py::test_main_window_edit_menu_exposes_the_editor_actions`
(`test_main_window.py:324`) and
`tests/test_actions.py::test_build_actions_contains_expected_shortcuts_and_states`
(`test_actions.py:11`). Where a task below explicitly authorizes updating one of
these, that update is required by this plan and is not a scope violation. Record
the rationale in the session log. Do not edit any other test's expected values.

### Task 0 — Move the cache root off the tmpfs and add a budget gate

Do this **before any other command in the round**, including before the first
`./run.sh` invocation.

1. Create the target directory:

   ```bash
   mkdir -p /home/beallio/.local/state/wherewolf-cache
   ```

   If this fails with a permission or sandbox error, **stop the round
   immediately** and report that `ORCH_ADD_DIRS` does not grant write access to
   `/home/beallio/.local/state`. Do not work around it by leaving the cache on
   the tmpfs.

2. Replace the tmpfs directory with the symlink, **preserving orchestration
   state**. `/tmp/wherewolf` is `ORCH_TMP_ROOT` (`orchestration.conf`), so it
   holds this run's own round-complete marker, finalized marker, and finalize
   journal (`scripts/orchestration/lib.sh:139`, `289`, `456`) alongside the
   caches. A blanket `rm -rf` would delete live orchestration state for the round
   you are currently executing. Do not use one.

   Orchestration state is plain files at depth 1; caches are directories. Move
   the files, then drop the directories:

   ```bash
   find /tmp/wherewolf -maxdepth 1 -type f -exec mv -t /home/beallio/.local/state/wherewolf-cache/ {} +
   rm -rf /tmp/wherewolf
   ln -s /home/beallio/.local/state/wherewolf-cache /tmp/wherewolf
   ```

   Do **not** try to `mv` the cache directories themselves: `/tmp` and `/home`
   are different filesystems, the venv is hardlinked into the uv cache, and a
   cross-device move would break the hardlinks and inflate the copy. Rebuilding
   is one `uv sync`.

   Confirm no orchestration state was lost. Capture the file list before the
   move and compare after:

   ```bash
   before=$(find /tmp/wherewolf -maxdepth 1 -type f -printf '%f\n' | sort)
   # ... perform the move, rm, and ln ...
   after=$(find /tmp/wherewolf/ -maxdepth 1 -type f -printf '%f\n' | sort)
   diff <(echo "$before") <(echo "$after") && echo "orchestration state preserved" || echo "STATE LOST"
   ```

   `STATE LOST` means stop and restore before continuing.

3. Rebuild the environment at the new location and confirm it works:

   ```bash
   ./run.sh uv sync --frozen
   ```

   Check the exit status of `uv sync` itself, not of a pipeline it feeds
   (see `references/verification-standards.md`, VS-07). Assign it:

   ```bash
   ./run.sh uv sync --frozen; sync_status=$?
   echo "uv sync exit: $sync_status"
   ```

   `sync_status` must be `0`. If it is non-zero, stop and report the error text.

4. Prove the relocation actually took effect. All three must hold:

   ```bash
   test -L /tmp/wherewolf && echo "symlink: yes" || echo "symlink: NO"
   readlink /tmp/wherewolf
   du -sb /home/beallio/.local/state/wherewolf-cache | awk '{print $1}'
   ```

   Expected: `symlink: yes`, a `readlink` of
   `/home/beallio/.local/state/wherewolf-cache`, and a byte count greater than
   `100000000` (the rebuilt venv and uv cache land there, so a near-zero count
   means the sync wrote somewhere else and the relocation failed).

5. Create the budget gate at `scripts/check_cache_budget.sh`, mode `0755`:

   - it must resolve the real path behind `/tmp/wherewolf` and print its size in
     bytes;
   - it must exit non-zero with the message
     `cache budget exceeded: <bytes> > <budget>` when the cache root exceeds
     4 GiB (`4294967296`);
   - it must exit non-zero with the message
     `cache root is not a symlink; it is back on the tmpfs` when
     `/tmp/wherewolf` is not a symlink;
   - it must use `set -euo pipefail` and must not use `grep -c ... || true`
     (VS-08) or infer status through a pipeline (VS-07).

6. Add `tests/test_cache_budget.py` covering the script's two failure paths and
   its success path, by invoking the script with a temporary directory
   substituted for the cache root (parameterise the root via an environment
   variable, e.g. `WHEREWOLF_CACHE_ROOT`, defaulting to `/tmp/wherewolf`). Assert
   on the **exact** failure strings above, not merely on a non-zero exit — a
   missing script also exits non-zero with no output (VS-02).

7. Commit: `chore(cache): relocate cache root off tmpfs and add budget gate`.

### Task 1 — Populate the File menu

In `main_window.py::_build_menus` (`main_window.py:887`):

- add `self.desktop_actions.add_datasets` to `file_menu` as its first item;
- add a separator, then a new `self.quit_action = QAction("Quit", self)` with
  `QKeySequence.StandardKey.Quit`, connected to `self.close`;
- move `self.desktop_actions.clear_history` out of `file_menu` and into
  `edit_menu`, appended after the existing `toggle_comment` entry behind a
  separator.

Assign the quit action to `self.quit_action` so tests can reach it.

Write `tests/test_main_window.py` tests asserting: `file_menu` contains the
add-datasets action and a quit action bearing the standard Quit sequence; the
quit action is connected such that triggering it closes the window; and
`clear_history` is no longer in `file_menu` but is in `edit_menu`.

This task changes Edit-menu contents, so
`test_main_window_edit_menu_exposes_the_editor_actions` (`test_main_window.py:324`)
will need its expected list extended with the moved `clear_history` entry. That
update is authorized.

Commit: `feat(desktop): populate the File menu with Add Datasets and Quit`.

### Task 2 — Add menu mnemonics

Change the five `menu_bar.addMenu(...)` calls to `"&File"`, `"&Edit"`,
`"&Query"`, `"&View"`, `"&Help"` (`main_window.py:890`, `894`, `931`, `942`,
`960`). Menu lookups elsewhere use `setObjectName`, so object-name lookups are
unaffected; verify that claim rather than assuming it, by grepping the tests for
`.title()` and for menu lookups by display text.

Add a test asserting each top-level menu's `title()` begins with `&` and that the
mnemonic letters are distinct across the five menus (a duplicate mnemonic is a
real defect Qt will not report).

If any existing test asserts a bare menu title, updating that assertion is
authorized under this task.

Commit: `feat(desktop): add keyboard mnemonics to the menu bar`.

### Task 3 — Show elapsed time while a query runs

In `MainWindow`:

- add a `QTimer` (`self._elapsed_timer`) with a 1000 ms interval and a
  monotonic start timestamp captured when status becomes `RUNNING`;
- in `_on_query_status_changed` (`main_window.py:441`), start the timer on
  `RUNNING` and stop it on every terminal status;
- on each tick, update the status bar to
  `Executing query... (<n>s)` where `<n>` is whole elapsed seconds;
- ensure the timer is stopped in `closeEvent` so it cannot outlive the window.

Use `time.monotonic()`, not wall-clock time.

Tests: assert the timer is inactive at rest; active after a `RUNNING` status
change; inactive again after `SUCCEEDED`, `FAILED`, and `CANCELLED`; and that the
status-bar text after a simulated tick matches the elapsed-seconds format. Drive
the timer directly rather than sleeping — do not add real delays to the suite.

Commit: `feat(desktop): show elapsed time while a query runs`.

### Task 4 — Distinguish a zero-row result from no result

Add `self.empty_result_banner`, a `QLabel` with objectName
`empty_result_banner`, inserted into the results page beside
`empty_catalog_banner` (`main_window.py:830`) and hidden by default. Follow the
existing show/hide pattern used by `SchemaPanel` (`schema_panel.py:185-201`).

In `_on_query_result_ready` (`main_window.py:453`), show it with the text
`Query returned 0 rows.` when the status is `SUCCEEDED` and the frame has zero
height; hide it in every other case, including `FAILED` and `CANCELLED` (the
error label already covers those, and two stacked banners would be worse than
none).

Tests: zero-row success shows the banner with that exact text; a non-empty
success hides it; a failure hides it; a cancellation hides it.

Commit: `feat(desktop): distinguish an empty result from no result`.

### Task 5 — Make drag-and-drop equivalent to Add Datasets

The goal is exactly one code path for "paths became datasets", reached from both
the menu/toolbar action and a file drop.

- In `CatalogDock`, add a signal carrying the add report, e.g.
  `datasets_added = pyqtSignal(object)`, and emit it from `add_paths`
  (`catalog_dock.py:86`) on every call, including calls that added nothing.
- In `MainWindow`, extract the post-add body of `_on_add_datasets`
  (`main_window.py:604-627`) — the alias status message, `save_last_dataset_directory`,
  the schema-worker queueing, the profile-on-load decision and
  `mark_profile_skipped` branch, and the warnings message — into a single
  `_handle_add_result(result)` method.
- Connect `catalog.datasets_added` to `_handle_add_result` in
  `_build_catalog_dock` (`main_window.py:347`).
- Rewrite `_on_add_datasets` so that after choosing paths it routes through
  `self.catalog.add_paths(paths)` rather than calling the catalog service
  directly, so both entry points converge.

Watch for a double-handling regression: after this change `_on_add_datasets`
must not also call `_handle_add_result` itself, or every menu-initiated add will
queue its schema workers twice.

Tests: dropping files onto the window queues schema work and emits the same
status message as the menu action; a menu-initiated add queues schema work
exactly once (assert the queued-worker count, which is what catches the
double-handling regression).

Commit: `refactor(desktop): route drag-and-drop through the add-datasets handler`.

### Task 6 — Report skipped duplicates

In `_handle_add_result` (created in Task 5), read `result.duplicates`
(`catalog_service.py:65`) and, when non-empty, include a status-bar message
naming the count and the skipped aliases or filenames. When the call added
nothing *and* skipped duplicates, the duplicate message must be the message
shown — the current code shows nothing at all in that case.

Tests: adding a path already in the catalog produces a status message mentioning
the duplicate; adding a mix of new and duplicate paths reports both the addition
and the skip.

Commit: `feat(desktop): report datasets skipped as duplicates`.

### Task 7 — Bound the shutdown wait

Rewrite `closeEvent` (`main_window.py:1056`) so closing cannot hang:

- cancel first, wait second. Call `self.query_controller.cancel()` and
  `self.export_controller.cancel()` **before** waiting on any worker, so a
  worker blocked inside DuckDB is asked to stop rather than merely having its
  event loop quit;
- give every `worker.wait()` an explicit millisecond timeout (use 5000 ms);
- if a worker does not finish within its timeout, proceed with shutdown rather
  than blocking, and record that via the existing status/message surface;
- keep the existing geometry, window-state, splitter-size, and font-size saves,
  and keep them reachable on the timeout path — settings must still persist when
  a worker overruns;
- stop the Task 3 elapsed timer here.

Tests: a worker that never finishes does not prevent `closeEvent` from
completing; settings-save calls still occur when a worker times out; the normal
path still joins workers and still saves.

Do not use a real 5-second sleep in the tests — inject a fake worker whose
`wait()` returns `False`.

Commit: `fix(desktop): bound the shutdown wait so quitting cannot hang`.

---

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

Verification standards live in the orchestration-plan-author skill at
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`
(not in this repo). The `VS-nn` identifiers cited in the tasks above refer to it.
Comply with those standards; do not restate them. Every step below must be able
to fail. Report actual output — pass/fail tallies, byte counts, error strings —
not the conclusion that something worked.

### V1 — Cache budget holds for the whole round (runs after every task)

```bash
scripts/check_cache_budget.sh; budget_status=$?
echo "cache budget exit: $budget_status"
```

Record the printed byte count after each of tasks 0-7 in the session log, as an
ordered list. A monotonically climbing number that approaches 4 GiB is a finding
worth reporting even if the gate never trips.

### V2 — Prove the budget gate can fail before trusting it

Run these **before** relying on V1 as evidence.

1. Point the gate at a directory larger than the budget (via
   `WHEREWOLF_CACHE_ROOT`) and confirm it exits non-zero and prints
   `cache budget exceeded:` followed by the byte count. Record the exact line.
2. Temporarily replace `/tmp/wherewolf` with a real directory, run the gate, and
   confirm it prints `cache root is not a symlink; it is back on the tmpfs` and
   exits non-zero. Restore the symlink afterwards and re-verify with
   `readlink /tmp/wherewolf`.

If either probe passes silently, the gate is decoration — fix it before
continuing.

### V3 — Mutation controls (run after the implementation is complete)

For each, revert the mutation immediately after recording the result. Each
mutation must turn the named tests **red**; a mutation that leaves the suite
green means that task's tests do not test it.

1. Delete the `add_datasets` line from `_build_menus` → Task 1 File-menu test
   fails.
2. Change one menu title back from `"&Query"` to `"Query"` → Task 2 mnemonic
   test fails.
3. Remove the `self._elapsed_timer.stop()` call on terminal status → Task 3
   timer-inactive-after-completion test fails.
4. Invert the zero-height condition in `_on_query_result_ready` → Task 4
   zero-row test fails.
5. Disconnect `catalog.datasets_added` from `_handle_add_result` → Task 5
   drop-queues-schema-work test fails.
6. Skip the `result.duplicates` branch → Task 6 duplicate-message test fails.
7. Restore the unbounded `worker.wait()` → Task 7 hanging-worker test fails or
   hangs. If it hangs rather than failing, note that the test needs its own
   timeout and add one.

Record, per mutation, the test node id that went red and the assertion message.
A mutation that produces a *collection* error rather than an assertion failure
does not count as a pass.

### V4 — Negative control (runs last)

After all mutations are reverted, run the full suite and record the pass/fail/
skip tallies verbatim from pytest's summary line:

```bash
./run.sh uv run pytest
```

This runs last, after the failure cases in V2 and V3, so a green result is not
merely the absence of exercise. Also record the final
`scripts/check_cache_budget.sh` byte count here.

### V5 — Manual GUI verification (DEFERRED, not performed by the implementer)

The following require a live display and are **not** verified by this plan.
State them as deferred in the session log; do not claim them as done.

- `Alt+F`, `Alt+E`, `Alt+Q`, `Alt+V`, `Alt+H` actually open their menus.
- The elapsed counter visibly increments during a slow query, and the number
  stops advancing the moment the result lands.
- Dragging a file from a file manager onto the window populates the schema panel
  without a further click.
- Closing the window mid-query returns the desktop promptly rather than freezing.
- The `Quit` action's platform-standard sequence resolves as expected on this
  desktop environment (`QKeySequence.StandardKey.Quit` is `Ctrl+Q` on X11/Wayland
  but is empty on some platforms; if it resolves empty here, report that rather
  than hardcoding a literal).

### Explicitly not verified

- No performance measurement of the results grid; grid virtualization is out of
  scope.
- No verification that the relocated cache survives a reboot. The tmpfs quota
  reverts to its 2387 MiB default on reboot; the symlink makes that irrelevant
  for this project, but the underlying mount option is untouched by this plan.
- Task 5 changes the call path for dataset registration. The plan asserts worker
  queueing counts but does **not** verify Spark-engine dataset registration,
  which is excluded from the default pytest run by the `not spark` marker in
  `pyproject.toml`.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished desktop-shell-ui-fixes
```

This writes:

```text
/tmp/wherewolf/desktop-shell-ui-fixes_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer desktop-shell-ui-fixes`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/desktop-shell-ui-fixes-review-*.md
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
   scripts/orchestration/clear-finished desktop-shell-ui-fixes
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
   git add docs/review/desktop-shell-ui-fixes-review-*.md
   git commit -m "docs(review): record desktop-shell-ui-fixes review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished desktop-shell-ui-fixes
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer desktop-shell-ui-fixes` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed desktop-shell-ui-fixes
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize desktop-shell-ui-fixes
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/desktop-shell-ui-fixes_finalized
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
scripts/orchestration/finalize desktop-shell-ui-fixes
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/desktop-shell-ui-fixes_finished
/tmp/wherewolf/desktop-shell-ui-fixes_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
