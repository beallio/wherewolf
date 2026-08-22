# Plan: Fix hidden-column selection copy and add cell inspector and selection statistics (results-grid-selection-fixes)

## Context

### Problem Definition

Three changes to the results grid, ordered so that the defect is fixed before the features that
would otherwise inherit it.

**1. Copying or exporting a selection returns the wrong column when a column is hidden.**
`ResultTableView.selection_for_export()` (`src/wherewolf/desktop/widgets/result_table_view.py:104`)
records each selected cell as `(source_row, header.visualIndex(column))`, but builds its
`column_order` map from **non-hidden** logical columns only. Qt's `visualIndex()` still counts
hidden sections, so the two indexings disagree: every hidden column to the left of a selection
shifts the lookup by one and a different column's data is returned.

Both consumers share the bug because both index the map by visual position:
`serialize_to_tsv()` at `src/wherewolf/desktop/clipboard_serializers.py:65` (backs `Ctrl+C`) and
`selected_frame()` at `src/wherewolf/services/selection.py:36` (backs `Export Selection…`).

Confirmed empirically before this plan was written — three columns `a, b, c`, column `a` hidden,
one cell selected in `b` (value 2):

```text
SELECTED_CELLS [(0, 1)]   COLUMN_ORDER [1, 2]   TSV '3'
```

The copy returns `3`, the value of `c`. Hiding a column is reachable from the results header
context menu, so this is reachable in normal use and silently corrupts copied and exported data.

**2. There is no way to read a cell whose value does not fit the grid.** JSON is a first-class
source format, so nested structs and long strings land in cells routinely and are elided. The user
must copy the value out to another program to read it.

**3. There is no selection summary.** Selecting a column of numbers reports nothing. Answering
"what do these sum to" requires editing the SQL and re-running, losing the current result.

### Architecture Overview

- Fix (1) at its origin, in `selection_for_export()`, so that `column_order[v]` is the model column
  at visual position `v` for **every** visual position. Both downstream consumers are then correct
  without being touched. Hidden columns stay excluded from `selected_cells`, so the extra entries
  in the map are never dereferenced.
- Build (3) on the corrected map plus the typed values `PolarsTableModel` already serves under
  `Qt.ItemDataRole.UserRole` (`src/wherewolf/desktop/models/polars_table_model.py:60`). Aggregate
  in one pass over the source `polars` frame, not per `QModelIndex`.
- Build (2) as a non-modal floating window modelled on `ValueCountsWindow`
  (`src/wherewolf/desktop/widgets/value_counts_window.py`), reusing its lifetime pattern:
  retention in a list on `MainWindow`, removal on close, bulk close on shutdown
  (`src/wherewolf/desktop/main_window.py:300,1227-1239,1891`).

### Core Data Structures

- `SelectionStatistics` — a new frozen dataclass in `src/wherewolf/domain/models.py`:
  `cell_count: int`, `distinct_count: int`, `null_count: int`, and
  `numeric: NumericSelectionStatistics | None` carrying `total`, `mean`, `minimum`, `maximum`.
  `numeric` is `None` unless every selected column is numeric.
- No change to `ExecutionRequest`, `QueryResult`, or any persisted format. Nothing in
  `~/.wherewolf/` or `QSettings` changes shape.

### Public Interfaces

- `ResultTableView.selection_for_export() -> tuple[list[tuple[int, int]], list[int]]` — signature
  unchanged; `column_order` is now addressable by visual index. Update its docstring to say so.
- `ResultTableView.selection_statistics() -> SelectionStatistics | None` — new. Returns `None` for
  an empty selection or a single cell.
- `ResultTableView.selection_stats_changed = pyqtSignal(object)` — new; emits the statistics or
  `None`.
- `CellInspectorWindow(value, column_name, parent)` — new widget in
  `src/wherewolf/desktop/widgets/cell_inspector_window.py`.
- `MainWindow` gains a `result_selection_stats_label` on the results page and an
  `inspect_cell` action.

### Dependency Requirements

None. No new runtime or dev dependency. `pyproject.toml` and `uv.lock` must not change.

### Scope Boundaries

In scope: the three items above.

Explicitly **out** of scope — do not implement, do not refactor toward:

- "Jump to the error position in the editor" and "Count all rows". They are separately planned and
  touch the editor diagnostic path and the query dispatch path respectively.
- Docking or embedding the inspector in the results page. The results page stays a flat
  `QVBoxLayout`; converting it to a `QSplitter` is not part of this round.
- Populating `QueryResult.total_row_count`, changing `QueryController`, or adding any new worker.
- Changing the `Ctrl+C` / export **ordering** semantics. Rows and columns keep their current
  deterministic visual-order rules; only the column-index resolution is being corrected.

**Slug used throughout this plan:** `results-grid-selection-fixes`

---

## Orchestration Contract

**Slug:** `results-grid-selection-fixes`

**Plan file:**

```text
docs/plans/2026-08-22_results-grid-selection-fixes.md
```

**Implementation branch:**

```text
feat/results-grid-selection-fixes
```

**Round-complete marker:**

```text
/tmp/wherewolf/results-grid-selection-fixes_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/results-grid-selection-fixes_finalized
```

**Review notes:**

```text
docs/review/results-grid-selection-fixes-review-*.md
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
git checkout -b feat/results-grid-selection-fixes
```

Commit this plan first:

```bash
git add docs/plans/2026-08-22_results-grid-selection-fixes.md
git commit -m "docs(plan): add results-grid-selection-fixes implementation plan"
```

---

## Implementation Tasks

Work in this order. Each numbered task is one atomic commit with a Conventional Commit message.
Follow strict TDD: write the failing test, run it and see it fail, then implement. Run every
command through `./run.sh`.

### 1. Establish the baseline

Record the starting state before changing anything:

```bash
set -o pipefail
git rev-parse HEAD
./run.sh uv run pytest -q 2>&1 | tail -3
```

Record the exact tally line. If the suite is not green at the start, stop and report — do not
begin work on a red baseline.

### 2. RED: prove the hidden-column selection defect

Add to `tests/test_result_table_view.py` a test named
`test_selection_for_export_maps_visual_columns_when_a_column_is_hidden`:

- build a `ResultTableView`, `set_frame(pl.DataFrame({"a": [1], "b": [2], "c": [3]}))`;
- `view.hide_column(0)`;
- select the proxy index at row 0, logical column 1 (`b`, value 2) through the selection model;
- call `view.selection_for_export()` and pass the result to `serialize_to_tsv(frame, cells, order)`;
- assert the text is exactly `"2"`.

Add a second test in the same file,
`test_selection_export_frame_maps_visual_columns_when_a_column_is_hidden`, doing the same but
passing the result to `wherewolf.services.selection.selected_frame` and asserting the returned
frame has column `b` with value 2 — `Export Selection…` goes through that path, not the TSV one.

Run them and confirm both fail:

```bash
set -o pipefail
./run.sh uv run pytest tests/test_result_table_view.py -q --no-cov \
  -k "hidden" 2>&1 | tail -5
```

Expected before the fix: 2 failed. Record the observed assertion text.

### 3. GREEN: correct the visual-to-model map

In `ResultTableView.selection_for_export()`
(`src/wherewolf/desktop/widgets/result_table_view.py:104`), build `column_order` over **all**
logical columns sorted by visual index, dropping the `if not self.isColumnHidden(logical)` filter
from that comprehension only. Leave the `selected_cells` loop unchanged — it must keep skipping
hidden columns, so the added entries are never dereferenced.

Update the docstring to state the returned map is indexed by visual position and includes hidden
columns.

Do not modify `serialize_to_tsv`, `selected_frame`, `ordered_selected_cells`, or
`selected_visual_columns`. If the two tests from task 2 do not both pass with the change confined
to `selection_for_export`, stop and report rather than editing the consumers.

Confirm the pre-existing ordering tests still pass:

```bash
set -o pipefail
./run.sh uv run pytest tests/test_result_table_view.py tests/test_clipboard_serializers.py \
  tests/test_preview_export.py tests/test_selection.py -q --no-cov 2>&1 | tail -3
```

Commit: `fix(results): resolve selected columns correctly when a column is hidden`.

### 4. RED then GREEN: selection statistics

Add `SelectionStatistics` and `NumericSelectionStatistics` frozen dataclasses to
`src/wherewolf/domain/models.py`, matching the field list in Context → Core Data Structures.

Write failing tests in `tests/test_result_table_view.py` first:

- a multi-cell selection over one numeric column reports `cell_count`, `distinct_count`, and
  numeric `total`, `mean`, `minimum`, `maximum`;
- a selection spanning a numeric and a string column reports counts with `numeric is None`;
- a selection containing nulls excludes them from the numeric aggregates and reports
  `null_count`;
- a single-cell selection and an empty selection both return `None`;
- **a selection taken while a column is hidden reports the statistics of the column the user
  actually selected** — this is the regression guard tying task 4 to task 3.

Then implement `ResultTableView.selection_statistics()` and the `selection_stats_changed` signal,
connected to `selectionModel().selectionChanged`. Resolve each selected cell's model column
through the corrected `column_order` map; aggregate with `polars` over the source frame in a
single pass rather than iterating `selectedIndexes()`.

In `MainWindow._build_central_area`, add `result_selection_stats_label` to the results page
immediately below `result_summary_label` (`src/wherewolf/desktop/main_window.py:1375`), hidden by
default, and connect it to the new signal. Do **not** route this through the status bar: 0.9.0
deliberately moved the result summary off the status bar because its ten-second timeout made it
disappear.

Add a `tests/test_main_window.py` test asserting the label becomes visible with the expected text
after a multi-cell selection and hides again when the selection is cleared.

Commit: `feat(results): summarise the current selection above the grid`.

### 5. RED then GREEN: cell value inspector

Write failing tests first, in a new `tests/test_cell_inspector_window.py`:

- the window renders a long string in full, not elided;
- a `dict`/`list` value is pretty-printed as indented JSON;
- a string that merely starts with `{` but is not valid JSON is shown verbatim rather than raising;
- a value larger than the size cap is truncated **and** the window says so;
- the copy button places the untruncated value on the clipboard.

Then add `src/wherewolf/desktop/widgets/cell_inspector_window.py` — a non-modal window with a
read-only monospace text area and a copy button. Take the raw value from
`Qt.ItemDataRole.UserRole`. **Do not render through
`clipboard_serializers.format_cell_value()`** — that function is TSV escaping, it stringifies
Python structures and doubles quotes, so JSON parsing downstream of it is unreliable.

Wire it up in `MainWindow` using the `ValueCountsWindow` lifetime pattern exactly: keep a
`_cell_inspector_windows` list, remove on close, and close them all in the existing shutdown path
alongside `_value_counts_windows` (`src/wherewolf/desktop/main_window.py:300,1227-1239,1891`).

Open it from the results body context menu (`result_table_view.py:257`) and a shortcut. The body
context-menu handler at `result_table_view.py:282` does not currently make the clicked cell
current, so set the index at the clicked position current before opening, or the window shows a
previously selected cell. Add a test for that specific behaviour: right-clicking cell B must
inspect B, not the cell selected beforehand.

Commit: `feat(results): add a cell value inspector`.

### 6. Documentation and session log

- Add an `## Unreleased` entry to `CHANGELOG.md` covering all three changes, leading with the
  copy defect and describing it in user terms (what was wrong, what it did to their data).
- Update the README's "Results grid and ordering" section to mention the selection summary and the
  inspector.
- Write `docs/agent_conversations/2026-08-22_results-grid-selection-fixes.json` with the date,
  objective, files modified, tests added (exact node ids), design decisions, and the measured
  results, following the shape of the existing files in that directory.
- Do not bump the version in `pyproject.toml` and do not tag. Releasing is a separate decision.

Commit: `docs(results): record selection fixes and inspector`.

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

Every step below must be able to fail. The standards these follow are in the orchestration
skill's `references/verification-standards.md`; do not restate them, apply them. Report the
**actual output** of each command — tallies, node ids, assertion text — not a conclusion that it
passed.

Run everything through `./run.sh`, and put `set -o pipefail` at the top of any snippet that pipes
a test command into `tail`, so a crash in pytest is not masked by a successful `tail`.

### 1. Gate proof: the new tests fail before the fix

Recorded in task 2. The two hidden-column tests must have been observed **failing** against the
unmodified `selection_for_export`. If they passed before the fix, they do not test what they
claim and must be rewritten.

Report: the pre-fix failure output, including the actual copied value the assertion reported.

### 2. Mutation: revert each change and confirm the right tests go red

Run these one at a time, restoring the file after each. Each mutation must fail the named tests
and no others.

**2a. Hidden-column fix.** Re-add the `if not self.isColumnHidden(logical)` filter to the
`column_order` comprehension in `selection_for_export`.

```bash
set -o pipefail
./run.sh uv run pytest tests/test_result_table_view.py -q --no-cov -k "hidden" 2>&1 | tail -5
```

Expected: the two task-2 tests and the hidden-column statistics test fail. Record the tally.
Restore the file and re-run to confirm they pass again.

**2b. Selection statistics.** Make `selection_statistics()` return `None` unconditionally.
Expected: the statistics tests and the `test_main_window.py` label test fail. Record the tally,
then restore.

**2c. Cell inspector.** Make the inspector render `str(value)` instead of pretty-printed JSON.
Expected: the JSON pretty-print test fails and the "not valid JSON" test still passes. Record
both, then restore.

If any mutation leaves the suite green, the corresponding tests are decoration — say so and fix
them rather than proceeding.

### 3. Confirm the defect is fixed in both consumers, not just one

The TSV path and the export path resolve columns through different functions. A fix that only
satisfies one of them is incomplete.

```bash
set -o pipefail
./run.sh uv run pytest tests/test_result_table_view.py tests/test_clipboard_serializers.py \
  tests/test_preview_export.py tests/test_selection.py tests/test_main_window.py \
  -q --no-cov 2>&1 | tail -3
```

Report the tally. State explicitly whether `selected_frame` is exercised with a hidden column by
one of the new tests — if it is not, the export path is unverified and must be said so.

### 4. Confirm nothing changed shape that should not have

```bash
git --no-pager diff --stat dev...HEAD -- pyproject.toml uv.lock
```

Expected output: nothing. Any diff here means a dependency changed, which is out of scope. Report
the actual output rather than asserting it was empty.

### 5. Negative control: the full suite, after every mutation is restored

Run last, after section 2 has restored every mutated file:

```bash
set -o pipefail
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
./run.sh uv run pytest 2>&1 | tail -3
```

Report the exact pytest tally line and each gate's own output. The baseline recorded in task 1 was
`648 passed, 7 deselected` at `462cc7d`; the final count must be that plus the tests added here,
with zero failures. A count that did not grow means tests were not added or were not collected.

### 6. Working tree and quality gates

```bash
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

`git status --short` must print nothing. Report its actual output.

### Deferred and unverified

State these explicitly in the round-complete report rather than leaving them implied:

- **No manual GUI verification is performed.** Every check above is headless via `pytest-qt`.
  Visual placement of the statistics label, the readability of the inspector at real window sizes,
  and native-dialog behaviour are unverified by this round.
- **Performance is unmeasured.** Whether `selectionChanged` fires often enough to matter on a
  100,000-row selection, and whether a multi-megabyte cell value stalls the inspector, are
  assumptions behind the single-pass aggregation and the size cap — neither is benchmarked here.
- **Spark is not exercised.** The suite runs with `-m 'not spark'`; none of these changes are
  engine-specific, but that is reasoning, not measurement.
- Whether any **other** caller resolves a column by visual index and shares the task-3 defect was
  not audited beyond the two consumers named in Context. Report if you find another.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished results-grid-selection-fixes
```

This writes:

```text
/tmp/wherewolf/results-grid-selection-fixes_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer results-grid-selection-fixes`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/results-grid-selection-fixes-review-*.md
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
   scripts/orchestration/clear-finished results-grid-selection-fixes
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
   git add docs/review/results-grid-selection-fixes-review-*.md
   git commit -m "docs(review): record results-grid-selection-fixes review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished results-grid-selection-fixes
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer results-grid-selection-fixes` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed results-grid-selection-fixes
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize results-grid-selection-fixes
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/results-grid-selection-fixes_finalized
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
scripts/orchestration/finalize results-grid-selection-fixes
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/results-grid-selection-fixes_finished
/tmp/wherewolf/results-grid-selection-fixes_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
