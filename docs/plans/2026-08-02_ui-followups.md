# Plan: History, completion popup, error display and toolbar fit (ui-followups)

## Context

Five defects reported against build `3d0b664`. Each was reproduced and measured before
this plan was written; the file:line references are verified.

### F1 — the toolbar controls disappear on a narrow window (REGRESSION)

The previous round removed the `QScrollArea` as asked, but the controls now vanish instead
of scrolling. Measured:

```text
window 1600px wide -> engine_selector visible=True
window 1400px wide -> engine_selector visible=False
toolbar sizeHint   -> 1449px
```

All six controls still exist and are still parented to the toolbar — they are simply hidden
behind Qt's overflow extension whenever the window is narrower than 1449px. **My round-02
review checked only that the controls existed, not that they were visible, which is why
this shipped.** Six labelled controls plus seven action buttons do not fit one row at any
reasonable window width.

Do not reintroduce a `QScrollArea` (`tests/test_main_window.py:81` forbids it, and the
maintainer rejected it). The controls must be reachable at ordinary window sizes without
hunting behind a `»` button.

### F2 — history columns cannot be resized

`widgets/history_dock.py:26` pins column 0:

```python
header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
```

`ResizeToContents` makes the section non-draggable.

### F3 — history timestamps show sub-second precision

`widgets/history_dock.py:41` renders `str(record["timestamp"])`, the raw stored value,
including microseconds.

### F4 — selecting a history entry also restores datasets and schemas

`main_window.py:714-719`: `_restore_history_query` places the SQL in the editor and then
calls `_restore_history_catalog(record)`, which runs `add_paths` and queues schema
inspection for every path in the record. The maintainer wants selecting a query to restore
**only the query text**.

### F5 — completion does not pop up while typing

This is a **display defect, not a missing feature**. The machinery is already present and
enabled:

```text
settings default  DEFAULT_COMPLETION_ENABLED = True
settings default  DEFAULT_COMPLETION_THRESHOLD = 2
sql_editor.py:74  self.textChanged.connect(self._on_text_changed_completion)
sql_editor.py:117 request_completion(forced=False) — gated on enabled + threshold
```

Preferences already exposes both settings (`main_window.py:116-118`). So typing `cus`
(3 characters, above the threshold of 2) should already request completion. It does not
visibly suggest anything. **Find out why the popup never appears** — likely candidates are
the QScintilla user-list/autocompletion source never being shown by
`widgets/completion_adapter.py`, or the results arriving asynchronously and being dropped.

### F6 — query errors are not shown in the results area

`main_window.py:461` reports failures only in the status line and Messages tab. The results
table keeps its previous contents or goes blank, so a user watching the grid sees no
explanation.

**Slug used throughout this plan:** `ui-followups`

---

## Orchestration Contract

**Slug:** `ui-followups`

**Plan file:**

```text
docs/plans/2026-08-02_ui-followups.md
```

**Implementation branch:**

```text
feat/ui-followups
```

**Round-complete marker:**

```text
/tmp/wherewolf/ui-followups_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/ui-followups_finalized
```

**Review notes:**

```text
docs/review/ui-followups-review-*.md
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
git checkout -b feat/ui-followups
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_ui-followups.md
git commit -m "docs(plan): add ui-followups implementation plan"
```

---

## Implementation Tasks

One commit per task. TDD: failing test first.

**Assert visibility, not just existence.** `findChild` returns hidden widgets, and that is
precisely how F1 shipped past a green review. Every test in this plan that concerns a
control being available must assert `isVisible()` (with the window shown and sized), not
merely that the object can be found.

### Task 1 — toolbar controls fit and stay visible (F1)

Rework the layout so all six controls are usable at ordinary window widths. Options:
put the query controls on a second toolbar row via `addToolBarBreak`, move the less-used
ones (editor theme, export format) into a menu or the Preferences dialog, or use compact
captions. **Do not use a `QScrollArea`.** State your choice and why in the session log.

Test at a realistic narrow width — construct the window, `show()` it, `resize(1024, 768)`,
process events, then assert every named control reports `isVisible() is True`. Add 1280 and
1440 as well. A test at 1600px would pass today and prove nothing.

### Task 2 — resizable history columns (F2)

Use `QHeaderView.ResizeMode.Interactive` (with a sensible default width) so the user can
drag the timestamp column. Test that the header's resize mode permits user resizing and
that setting a section size takes effect.

### Task 3 — second-precision timestamps (F3)

Render history timestamps truncated to the second. Parse the stored value rather than
string-slicing it, and keep the full value in the row's tooltip. Test with a stored
timestamp carrying microseconds and assert the displayed cell has none while the tooltip
retains the original.

### Task 4 — history restores only the query (F4)

`_restore_history_query` must place the SQL in the editor and do nothing else — no
`add_paths`, no `_queue_schema_work`, no catalog mutation.

Test that with a catalog already loaded, selecting a history record whose stored catalog
differs leaves `self._catalog_service.entries` **unchanged** and queues no schema work, while
the editor text updates. Assert on the catalog being untouched; that is the actual
complaint.

Keep `_restore_history_catalog` only if something else calls it; if nothing does, delete it
rather than leaving dead code.

### Task 5 — make the completion popup appear (F5)

Diagnose first, then fix. The settings and the `textChanged` wiring are already correct, so
do not "fix" them. Establish where the chain breaks between `request_completion(forced=False)`
and a visible list — inspect `widgets/completion_adapter.py` and how results reach
QScintilla.

Then make typing `cus` with a `customers` dataset loaded show `customers` as a suggestion,
and likewise for SQL keywords and functions. Keep it on by default (it already is) and keep
the Preferences toggle working.

Test through the editor: set a catalog, type a prefix, and assert the completion list is
**showing** and contains the expected entry. Asserting that a service returned candidates is
not sufficient — that already passes today while the user sees nothing.

### Task 6 — show query errors in the results area (F6)

On failure, display the error message where the results grid is, so it is visible without
switching to Messages. Keep the existing status line and Messages behaviour.

Test that after a failed query the results area exposes text containing the engine's error
message, and that a subsequent successful query clears it.

### Cross-cutting requirements

- Do not weaken, skip or delete existing tests.
- Do not reintroduce a `QScrollArea` in the toolbar.
- Do not remove `timid = true`, the `pyarrow` import, or the overwrite confirmation.
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

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check .
./run.sh uv run pytest
```

Record in the session log:

1. `isVisible()` for all six controls at 1024, 1280, 1440 and 1600 px window widths.
2. The history header's resize mode, and a section width before and after a programmatic resize.
3. A displayed timestamp cell and its tooltip for a record stored with microseconds.
4. `catalog_service.entries` before and after selecting a history record, plus the editor text.
5. The completion list's visibility and contents after typing `cus` with `customers` loaded.
6. The results-area text after a failed query, and after the next successful one.

**Negative controls are mandatory for tasks 1, 4, 5 and 6**, run against the **full** suite:
shrink the toolbar fix and confirm the visibility test fails; restore the catalog-restoring
call and confirm task 4 fails; break the popup display and confirm task 5 fails; suppress
the results-area error and confirm task 6 fails.

Confirm each mutation actually modified the file before trusting its result. Several times
this session a mutation that failed to apply looked exactly like a guard that does not bite,
and once a mutation targeted the wrong thing entirely (a column header rather than the cell
values). If a mutation reports no failures, first prove it changed the code.

## Deferred

Visual composition of the reworked toolbar, and how the completion popup looks in use, are
manual maintainer checks. Note them in `docs/review/manual-acceptance-checklist.md`.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished ui-followups
```

This writes:

```text
/tmp/wherewolf/ui-followups_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer ui-followups`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/ui-followups-review-*.md
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
   scripts/orchestration/clear-finished ui-followups
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
   git add docs/review/ui-followups-review-*.md
   git commit -m "docs(review): record ui-followups review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished ui-followups
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer ui-followups` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed ui-followups
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize ui-followups
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/ui-followups_finalized
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
scripts/orchestration/finalize ui-followups
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/ui-followups_finished
/tmp/wherewolf/ui-followups_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
