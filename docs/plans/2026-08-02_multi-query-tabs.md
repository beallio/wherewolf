# Plan: Multi-query tabs with per-tab results (multi-query-tabs)

## Context

The app has one SQL editor and one results area. A user working on several questions at
once keeps intermediate steps in comments, or loses them. This introduces query tabs, each
with its own editor and its own results.

This is the largest structural change since the desktop cutover: it touches the central
widget, the execution controller, the toolbar controls and persistence. Read this section
fully before writing code.

### What the code already settles

- **The catalog is app-wide.** `CatalogService` lives on `MainWindow` and datasets are
  registered per execution request. Tabs share one catalog; do not make it per-tab.
- **Execution is serialized today.** `query_controller.py:55-61` returns `False` when
  `self._status is not ExecutionStatus.IDLE`, so a second query cannot start while one runs.
- **History is app-wide.** `storage/history.py` records every executed query with a stable
  UUID; it is not scoped to any editor.
- **Persistence precedent exists.** `HistoryManager.DEFAULT_PATH` is
  `~/.wherewolf/history.json`, written as versioned JSON with migration helpers
  (`_migrate_v1_entry`, `_is_v2_entry`). Tab persistence follows that shape, not QSettings —
  SQL bodies do not belong in an INI/registry value.

### Maintainer decisions

These were settled by the maintainer and are not open:

1. **One query at a time, shared controller.** Keep the single `QueryController`. Running in
   one tab disables Run in the others until it completes or is cancelled. Do **not** create a
   controller per tab.
2. **Each tab is independent for its controls.** Engine, input dialect, preview row limit and
   export format are **per tab**. Switching tabs must show that tab's values.
3. **Tabs survive restart.** Tab SQL text, titles and order are restored on launch.

### The consequence that makes this hard

Because the controls are per-tab but the toolbar is global, the toolbar becomes a **view onto
the active tab's state**. Switching tabs must update the controls without those updates being
mistaken for user edits — a naive implementation writes the outgoing tab's values into the
incoming tab via `currentIndexChanged`. `QSignalBlocker` is already used for exactly this
reason in `desktop/widgets/schema_panel.py:72`.

**Slug used throughout this plan:** `multi-query-tabs`

---

## Orchestration Contract

**Slug:** `multi-query-tabs`

**Plan file:**

```text
docs/plans/2026-08-02_multi-query-tabs.md
```

**Implementation branch:**

```text
feat/multi-query-tabs
```

**Round-complete marker:**

```text
/tmp/wherewolf/multi-query-tabs_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/multi-query-tabs_finalized
```

**Review notes:**

```text
docs/review/multi-query-tabs-review-*.md
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
git checkout -b feat/multi-query-tabs
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_multi-query-tabs.md
git commit -m "docs(plan): add multi-query-tabs implementation plan"
```

---

## Implementation Tasks

One commit per task, in this order. TDD: write the failing test first, watch it fail, then
implement. Tests reach the feature from `MainWindow` the way a user would.

Tasks 1–3 are structural and must land before the rest. Do not start task 4 until switching
tabs demonstrably preserves each tab's SQL.

### Task 1 — a query tab model

Add a `QueryTab` type holding: a stable id, a title, SQL text, engine, source dialect,
preview limit, export format, and the last `QueryResult` (or `None`). Nothing Qt-specific in
this type — it is the thing that gets persisted and restored.

Test that a tab round-trips through serialisation with every field preserved, including a
`None` result and a non-default engine.

### Task 2 — tabbed editors with per-tab results

Replace the single editor/results pair in `_build_central_area` (`main_window.py:660`) with a
`QTabWidget` of query tabs. Each tab owns its own `SqlEditor` and its own results area —
results grid, Messages, Translation, preview filter and the export controls that moved there.

Provide New Tab, Close Tab and rename (double-click the tab header). Closing the last tab
leaves one empty tab rather than an empty window. Default titles like `Query 1`, `Query 2`.

Test: create two tabs, put different SQL in each, switch between them, and assert each
editor keeps its own text and each results area keeps its own frame. Assert on both tabs
after switching — checking only the active one would pass with a single shared editor.

### Task 3 — toolbar controls follow the active tab

Engine, input dialect, preview limit and export format now read from and write to the active
tab. On tab switch, update every control from the incoming tab's values **inside a
`QSignalBlocker`**, so the update does not fire `currentIndexChanged` and overwrite the tab
that was just activated.

Test the specific trap: set tab 1 to DuckDB and tab 2 to Spark, switch 1 → 2 → 1, and assert
both tabs still hold their original engine. Do the same for preview limit with two different
numbers. A test that only switches once will not catch the write-back bug.

### Task 4 — serialized execution across tabs

Keep the single `QueryController`. While a query runs, Run must be disabled in **every** tab,
and Cancel must cancel the running query regardless of which tab is active. When it finishes,
the result must be delivered to the tab that submitted it — **not** to whichever tab is active
when it completes.

Test: start a query from tab 1, switch to tab 2 before it completes, and assert the result
lands in tab 1 and tab 2's results are untouched. That is the defect this task exists to
prevent.

Also test that Run is disabled in tab 2 while tab 1 is running, and re-enabled afterwards.

### Task 5 — persist and restore tabs

Persist tabs to `~/.wherewolf/tabs.json`, following `storage/history.py`: a schema version,
atomic write, and tolerance for a malformed or absent file. Store SQL text, title, order,
engine, dialect, preview limit and export format. Do **not** persist results.

On launch, restore the tabs and the previously active index. A corrupt file must yield one
empty tab and a message, never a crash on startup.

Test: write tabs, simulate a restart by constructing a fresh `MainWindow` against the same
storage path, and assert titles, order, SQL and per-tab settings are restored. Separately,
write a deliberately corrupt file and assert the app still starts with one empty tab.

Use a temporary storage path in tests. `tests/conftest.py` already redirects
`HistoryManager.DEFAULT_PATH` for exactly this reason — do the same here, or the suite will
read and overwrite the maintainer's real tabs.

### Task 6 — history and schema still work across tabs

Selecting a history entry must load the SQL into the **active** tab only, leaving other tabs
untouched (history restores query text only — it must not touch the catalog). The schema
panel and catalog remain app-wide and unchanged.

Test that restoring history into tab 2 leaves tab 1's SQL unchanged.

### Cross-cutting requirements

- Do not create a `QueryController` per tab.
- Do not make the catalog, schema panel or history per-tab.
- Do not persist query results.
- Do not weaken, skip or delete existing tests. Where an existing test assumes a single
  editor, update it to address the active tab rather than deleting it.
- Do not remove `timid = true`, the `pyarrow` import, or the overwrite confirmation.
- Do not reintroduce a `QScrollArea` in the toolbar.
- Do not change `EngineKind` or the sqlglot identifiers in `DIALECT_MAPPING`.
- Do not bump the version, tag, or touch `main`.
- Run `./run.sh uv run ty check .` (whole repo) before committing.

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

Run the gates and record the actual tallies, not a conclusion:

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check .
./run.sh uv run pytest
```

Record in the session log, as literal output:

1. Both tabs' editor text after creating two tabs and switching between them.
2. Each tab's engine and preview limit after switching 1 → 2 → 1.
3. Which tab receives a result when the query is submitted from tab 1 and tab 2 is active on
   completion, plus tab 2's result state.
4. `run.isEnabled()` in tab 2 while tab 1 is running, and after it completes.
5. Tab titles, order, SQL and per-tab settings after a simulated restart.
6. The startup outcome against a deliberately corrupted `tabs.json` — tab count and the
   message shown.
7. Tab 1's SQL before and after restoring a history entry into tab 2.

### Negative controls — mandatory

Run each against the **full** suite and record the tally. Before trusting any result,
**prove the mutation changed the code** — print the mutated line or a boolean confirming the
edit applied. Several times in this project a mutation that failed to apply looked identical
to a guard that does not bite, and one targeted the wrong thing entirely and reported a false
pass.

| mutate | expected |
|---|---|
| remove the `QSignalBlocker` around the tab-switch control update | task 3's test fails |
| deliver results to the active tab instead of the submitting tab | task 4's test fails |
| skip writing `tabs.json` on change | task 5's restore test fails |
| let history restore write to all tabs | task 6's test fails |

A mutation that fails a large number of tests is weak evidence — it may have broken
construction rather than behaviour. Prefer a mutation that fails one or two targeted tests,
and say so if you cannot achieve that.

## Deferred

Explicitly **not** covered and to be stated as such:

- Concurrent execution across tabs. The controller stays serialized by decision, so no test
  exercises two queries running at once.
- Save/Open session files. Persistence is automatic only; there is no user-facing session
  format.
- Result persistence. Results are discarded on exit by design.
- Visual quality of the tab bar at many open tabs, tab overflow behaviour, and drag-to-reorder
  are manual maintainer checks.
- Behaviour with a very large number of tabs (memory held by per-tab result frames) is
  unmeasured.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished multi-query-tabs
```

This writes:

```text
/tmp/wherewolf/multi-query-tabs_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer multi-query-tabs`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/multi-query-tabs-review-*.md
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
   scripts/orchestration/clear-finished multi-query-tabs
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
   git add docs/review/multi-query-tabs-review-*.md
   git commit -m "docs(review): record multi-query-tabs review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished multi-query-tabs
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer multi-query-tabs` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed multi-query-tabs
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize multi-query-tabs
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/multi-query-tabs_finalized
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
scripts/orchestration/finalize multi-query-tabs
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/multi-query-tabs_finished
/tmp/wherewolf/multi-query-tabs_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
