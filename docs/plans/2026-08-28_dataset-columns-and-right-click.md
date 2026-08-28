# Plan: Resizable dataset columns and right-click targeting (dataset-columns-and-right-click)

## Context

Two changes to the dataset panel, both empirically verified against the running widget.
These are items **3a** and **3c** of a five-item user report. Item **3b** (multi-selection
batch actions) is a separate later plan and is **explicitly out of scope** here.

The GUI is **PyQt6 + QScintilla**, not PySide6. The panel the user calls the "dataset
window" is `CatalogDock` (`src/wherewolf/desktop/widgets/catalog_dock.py:30`), a `QTableView`
over `CatalogModel` with five columns: `Alias`, `File`, `Folder`, `Format`, `Schema status`.

### Change 3a — only 2 of 5 columns are user-resizable

The user's requirement is literal: *"All columns in the dataset window should be able to be
resized."* Current configuration:

```python
# src/wherewolf/desktop/widgets/catalog_dock.py:52-60
header = self._view.horizontalHeader()
if header is not None:
    header.setSectionsMovable(True)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    header.resizeSection(1, 220)
```

Measured by attempting a resize on each section at a 900 px dock width:

| # | Column | Mode | Width before → after | User-resizable |
| --- | --- | --- | --- | --- |
| 0 | Alias | Interactive | 100 → 160 | yes |
| 1 | File | Interactive | 220 → 280 | yes |
| 2 | Folder | Stretch | 304 → 304 | **no** |
| 3 | Format | ResizeToContents | 49 → 49 | **no** |
| 4 | Schema status | ResizeToContents | 93 → 93 | **no** |

`Stretch` and `ResizeToContents` both make a section non-draggable, so the fix is to make all
five `Interactive` with explicit default widths.

**Two consequences of the user's requirement, both accepted, neither negotiable:**

1. **Folder no longer auto-grows with the dock.** That behaviour comes from `Stretch`, which is
   mutually exclusive with user resizing. Verified: with all five `Interactive`, widening the
   dock from 900 px to 1300 px leaves Folder at 337 px.
2. **A narrow dock now shows a horizontal scrollbar.** Default widths total 910 px, so at the
   450 px dock width used by an existing test the columns no longer squeeze to fit. This is the
   correct trade — legible fixed columns plus a scrollbar beats illegibly squeezed columns —
   but it is a visible change.

**Do not** use `setStretchLastSection(True)`: it forces the last section to fill and thereby
makes `Schema status` non-resizable, re-creating the bug at a different column. **Do not** add
auto-fit or `resizeColumnsToContents` machinery; it fights the user's manual widths.

Default widths to use, verified as applied exactly and individually drag-resizable afterwards:

| # | Column | Default | Rationale |
| --- | --- | --- | --- |
| 0 | Alias | 120 | Aliases are file stems; 100 was the Qt default, not a considered value. |
| 1 | File | **220** | **Must stay 220** — two existing tests derive expected elision from `sectionSize(1) - 8`. |
| 2 | Folder | 300 | Approximates the 304 px `Stretch` produced at a 900 px dock. |
| 3 | Format | 90 | Longest content is `parquet` (7 chars); header `Format` is 6. |
| 4 | Schema status | 180 | Header is 13 chars; longest fixed content is `Unavailable — file not found` (28). |

`Format` renders only `SourceFormat` values — `csv`, `parquet`, `json`, `jsonl`, `xlsx`
(`src/wherewolf/domain/enums.py:15-20`). `Schema status` renders `Loading`, `Ready`,
`Unavailable — file not found`, or `Error: {schema_error}`
(`src/wherewolf/desktop/models/catalog_model.py:143-151`); the error branch is **unbounded**,
which is a further argument against `ResizeToContents` — one long error message currently blows
the column out.

`setSectionResizeMode`, `resizeSection`, `sectionSize` and `sectionResizeMode` all take
**logical** section indices, so user column reordering (`setSectionsMovable(True)`, asserted by
`tests/test_main_window.py:1329-1346`) does not interact with this change. Keep
`setSectionsMovable(True)`.

### Change 3c — right-click acts on the wrong row

`_on_context_menu(position)` never consults `position` for targeting; it resolves the target
purely from `currentIndex()`:

```python
# src/wherewolf/desktop/widgets/catalog_dock.py:183-186
def _on_context_menu(self, position: QPoint) -> None:
    selection = self._selected_entry()
    menu = QMenu(self)
```

`position` is used only at line 208 for `viewport.mapToGlobal(position)`. So right-clicking a
different row than the current one silently operates on the **previous** row.

Reproduced end-to-end against the real widget: seed 4 datasets, `view.selectRow(0)`, then call
`dock._on_context_menu(view.visualRect(model.index(3, 1)).center())` →
`dock._selected_entry()` returns row **0**, not the clicked row 3. Every one of the seven
context actions inherits this.

**Coordinate space is settled, do not re-derive it.** A real `QContextMenuEvent` sent to
`view.viewport()` delivers `customContextMenuRequested` with the *identical* viewport-relative
point (measured delta `QPoint(0, 0)` for rows 0, 2 and 3), and `view.indexAt(received_pos)`
returns the correct row each time. `view.visualRect(index)` also returns viewport coordinates.
So `self._view.indexAt(position)` is correct **with no translation**, even though
`viewport.pos()` within the view is `QPoint(13, 22)`.

**Row membership must be tested with `rowIntersectsSelection`, not the obvious alternatives.**
`selectionBehavior` is `SelectItems` (`catalog_dock.py:64`), so a row is represented by
individual cells and the clicked cell may be unselected while its row is selected. Measured
with only cell `(1, 2)` selected:

| Call | Result | Verdict |
| --- | --- | --- |
| `isSelected(index(1, 0))` | `False` | wrong — misses the row |
| `isRowSelected(1)` | `False` | wrong — demands every cell |
| `rowIntersectsSelection(1)` | `True` | **correct** |
| `rowIntersectsSelection(0)` | `False` | correct negative |

`rowIntersectsSelection` accepts a single argument in PyQt6 (verified; the Qt 5 two-argument
form is not needed).

### Non-goals

- **No multi-selection batch actions.** `_selected_entry()` keeps its single-entry contract and
  its signature. Do not add `remove_many`, do not touch `CatalogService`, do not change
  `selectionBehavior` from `SelectItems`, do not introduce `SelectionFlag.Rows` or
  `selectedRows()`. That is plan 3b.
- **No column-width persistence.** Verified absent: `MainWindow.saveState()`/`restoreState()`
  (`main_window.py:2289-2297, 2368-2370`) persists dock layout only, never `QHeaderView`
  section sizes, and no `header().saveState()` call exists anywhere. Columns 0 and 1 are
  already Interactive and already forgotten on restart, so this change does not regress
  anything — but resized widths will still not survive a restart. Separate plan if wanted.
- No changes to `setStretchLastSection`, the `FolderColumnDelegate` on column 2,
  `setTextElideMode`, `setSectionsMovable`, drag-and-drop, or any action's behaviour.
- Items 2 and 5 of the original report are not in this plan.

**Slug used throughout this plan:** `dataset-columns-and-right-click`

---

## Orchestration Contract

**Slug:** `dataset-columns-and-right-click`

**Plan file:**

```text
docs/plans/2026-08-28_dataset-columns-and-right-click.md
```

**Implementation branch:**

```text
feat/dataset-columns-and-right-click
```

**Round-complete marker:**

```text
/tmp/wherewolf/dataset-columns-and-right-click_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/dataset-columns-and-right-click_finalized
```

**Review notes:**

```text
docs/review/dataset-columns-and-right-click-review-*.md
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
git checkout -b feat/dataset-columns-and-right-click
```

Commit this plan first:

```bash
git add docs/plans/2026-08-28_dataset-columns-and-right-click.md
git commit -m "docs(plan): add dataset-columns-and-right-click implementation plan"
```

---

## Implementation Tasks

Work in order. All commands run from the repository root through the wrapper, e.g.
`./run.sh uv run pytest tests/test_catalog_dock.py`. Follow Red-Green-Refactor: write the
failing test first and record the observed failure before the production change. Commit
atomically with Conventional Commits.

`tests/test_catalog_dock.py` currently contains **18 tests**. Track that number.

### Task 1 (RED) — failing test for right-click targeting

Do 3c first: it is a correctness fix, needs no decisions, and is independent of the header work.

Add to `tests/test_catalog_dock.py`. **Critical harness details, verified — get these wrong and
your test will silently never fire:**

- `qtbot.mouseClick(viewport, Qt.MouseButton.RightButton, ...)` does **NOT** emit
  `customContextMenuRequested` under the offscreen platform. Do not use it.
- Drive the handler either directly as `dock._on_context_menu(point)`, or with a real event:
  `QApplication.sendEvent(view.viewport(), QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point))`.
  Both work; the event form is verified to deliver the identical point.
- `point` must be `view.visualRect(model.index(row, col)).center()` — viewport coordinates.
- `monkeypatch.setattr(QMenu, "popup", lambda self, pos: None)` so no real popup blocks the run.

Add these tests:

1. `test_catalog_right_click_targets_the_clicked_row_not_the_current_row` — seed 4 datasets,
   `view.selectRow(0)`, right-click row 3, assert `dock._selected_entry()[1] == 3`. Assert the
   alias too, so the failure message names the wrong dataset.
2. `test_catalog_right_click_on_an_unselected_row_selects_only_that_row` — with row 0 selected,
   right-click row 2; assert every index in `selectionModel().selectedIndexes()` has
   `row() == 2`.
3. `test_catalog_right_click_inside_the_existing_selection_preserves_it` — select cell `(1, 2)`
   only, then right-click cell `(1, 0)` (same row, different column, itself unselected).
   Assert the selected-index set is **unchanged** (still exactly `{(1, 2)}`) and that
   `_selected_entry()[1] == 1`. This is the test that fails if the implementer reaches for
   `isSelected` or `isRowSelected` instead of `rowIntersectsSelection`.
4. `test_catalog_right_click_on_blank_space_disables_every_context_action` — right-click well
   below the last row (e.g. `QPoint(50, view.viewport().height() - 5)`; assert first that
   `view.indexAt(point)` is invalid so the precondition is real). Assert all seven actions
   report `isEnabled() is False`: `_rename_action`, `_remove_action`, `_refresh_action`,
   `_copy_alias_action`, `_copy_path_action`, `_reveal_action`, `_insert_alias_action`.
   Note a prior row was selected, so this only passes if the handler ignores the stale
   `currentIndex()`.

Run `./run.sh uv run pytest tests/test_catalog_dock.py -q` and record failures. Expected: 1, 2
and 4 fail; 3 may pass by accident. If test 1 passes, stop and report — the premise is wrong.

### Task 2 (GREEN) — anchor the context menu on the clicked row

In `src/wherewolf/desktop/widgets/catalog_dock.py`, line 9 is currently
`from PyQt6.QtCore import QMimeData, QPoint, Qt, QUrl, pyqtSignal` — add
`QItemSelectionModel` to it. Then replace **only** line 184 (`selection = self._selected_entry()`)
with the anchoring block. Leave the seven `setEnabled(selection is not None)` calls
(`:187-193`), the menu assembly (`:195-203`), and the `popup` call (`:205-208`) untouched:

```python
    def _on_context_menu(self, position: QPoint) -> None:
        selection = self._resolve_context_target(position)
        menu = QMenu(self)
        ...
```

Add the helper next to `_selected_entry`:

```python
    def _resolve_context_target(self, position: QPoint) -> tuple[CatalogEntry, int] | None:
        """Anchor the context menu on the right-clicked row.

        A blank-space click must not inherit a stale ``currentIndex()``, so it resolves to
        ``None`` rather than deferring to :meth:`_selected_entry`.
        """
        index = self._view.indexAt(position)
        if not index.isValid():
            return None
        selection_model = self._view.selectionModel()
        if selection_model is None:
            return None
        # SelectItems means a selected row may have no selected cell in the clicked column,
        # so test row membership, not cell membership.
        already_selected = selection_model.rowIntersectsSelection(index.row())
        selection_model.setCurrentIndex(
            index,
            QItemSelectionModel.SelectionFlag.NoUpdate
            if already_selected
            else QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        return self._selected_entry()
```

Do not change `_selected_entry()`. Do not add `SelectionFlag.Rows`. Do not use `isSelected` or
`isRowSelected` — both are measured wrong for this view's `SelectItems` behaviour.

Re-run the file and record tallies. All four new tests plus all 18 pre-existing tests pass.

Commit: `fix(catalog): target the right-clicked dataset row in the context menu`.

### Task 3 (RED) — failing test for all-column resizing

`tests/test_catalog_dock.py:85-109` is
`test_catalog_file_column_is_resizable_and_folder_column_stretches`. Its assertions at lines
96, 97, 98 (Stretch / ResizeToContents modes) and line 105 (Folder grows with the dock) assert
exactly the behaviour this plan removes. **This plan authorises rewriting that test** — this is
the one sanctioned exception to the "never edit a test's expected value" rule, because the
behaviour it guards is being deliberately replaced. Record the rationale in the session log.

Replace it with `test_catalog_all_columns_are_user_resizable`:

- Keep `dock.show()` and `assert header is not None`.
- Assert `header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive` for every
  `column in range(dock.model.columnCount())` — derive the count from the model, do not
  hardcode 5.
- Delete the two `dock.resize(...)` calls, both `QApplication.processEvents()` calls,
  `narrow_folder_width`, and the Folder-growth assertion at line 105.
- Add a loop that, for every column, records `header.sectionSize(column)`, calls
  `header.resizeSection(column, before + 37)`, and asserts the new size is exactly
  `before + 37`. This proves each of the five resize paths, which is the user-visible contract.
- Keep `assert isinstance(view.itemDelegateForColumn(2), FolderColumnDelegate)`.

Add two more tests:

5. `test_catalog_default_column_widths_are_applied` — assert each
   `header.sectionSize(i)` equals `CatalogDock.DEFAULT_COLUMN_WIDTHS[i]`. Read the expected
   values from the class constant, not from literals duplicated in the test.
6. `test_catalog_widening_the_dock_leaves_user_column_widths_alone` — resize the dock from
   700 px to 1200 px and assert every section size is unchanged. This pins consequence (1) from
   the Context so it cannot silently regress back to `Stretch`.

Leave `test_catalog_file_column_keeps_basenames_visible_in_the_middle` (`:56-82`) and
`test_catalog_file_column_shows_complete_basenames_at_user_dock_width` (`:112-140`) **unchanged**.
Both derive expected elision from `header.sectionSize(1) - 8` and must keep passing — that is
why the File default must remain 220. If either fails, your File default is wrong; fix the
default, do not weaken those assertions.

Run and record. Expected: the rewritten test and tests 5 and 6 fail.

### Task 4 (GREEN) — make all five columns Interactive

In `src/wherewolf/desktop/widgets/catalog_dock.py`, add a class constant beside the existing
class attributes:

```python
    #: Default width per logical column; all columns are user-resizable from here.
    DEFAULT_COLUMN_WIDTHS: ClassVar[tuple[int, ...]] = (120, 220, 300, 90, 180)
```

`typing` is not currently imported in this module, so add `from typing import ClassVar` as a new
first-party import above the `PyQt6` imports, matching the module's existing import grouping
(ruff will confirm the ordering). Then replace the header block at
lines 55-60 with a loop that sets every logical column `Interactive` and applies the default
width. Keep `header.setSectionsMovable(True)` on line 54 exactly as-is:

```python
            for column, width in enumerate(self.DEFAULT_COLUMN_WIDTHS):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
                header.resizeSection(column, width)
```

Add an assertion or comment tying `len(DEFAULT_COLUMN_WIDTHS)` to `CatalogModel._COLUMNS` so
the two cannot drift; if a future column is added without a width, that must be a loud failure,
not a silently unsized column. A module-level or `__init__` guard such as
`assert len(self.DEFAULT_COLUMN_WIDTHS) == self._model.columnCount()` is acceptable.

Do not add `setStretchLastSection`, `resizeColumnsToContents`, or any auto-fit call.

Run and record. Rewritten test plus tests 5 and 6 pass; the two basename tests still pass.

Commit: `feat(catalog): make every dataset column user-resizable`.

### Task 5 — documentation and session log

- Add a `### Fixed` and/or `### Changed` entry under the existing `## Unreleased` heading in
  `CHANGELOG.md`, following the released sections' user-visible prose style. The horizontal
  scrollbar at narrow dock widths and the loss of Folder auto-stretch are **user-visible** and
  must be mentioned, not hidden.
- Only touch `README.md` if it documents dataset-panel columns; check first.
- Write the session log required by `AGENTS.md` §14 to
  `docs/agent_conversations/2026-08-28_dataset-columns-and-right-click.json`: date, objective,
  files modified (**including this plan file**), tests added, design decisions — specifically
  why `rowIntersectsSelection` rather than `isSelected`/`isRowSelected`, why no
  `setStretchLastSection`, and the rationale for rewriting the Folder-stretch test — and
  results. List every commit sha you created.

Commit: `docs: record dataset-columns-and-right-click changes`.

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

Run after the Quality Gates above pass. Every step must be able to fail; see
`references/verification-standards.md`. Record **actual output** — tallies, failing test names,
observed values — never a bare conclusion.

### V1 — mutation: prove the right-click anchoring is load-bearing

Temporarily restore `selection = self._selected_entry()` as the first line of
`_on_context_menu` (leaving `_resolve_context_target` defined but unused) and run:

```bash
./run.sh uv run pytest tests/test_catalog_dock.py -q -k "right_click"
```

Expected failure: `test_catalog_right_click_targets_the_clicked_row_not_the_current_row`,
`test_catalog_right_click_on_an_unselected_row_selects_only_that_row`, and
`test_catalog_right_click_on_blank_space_disables_every_context_action` fail. Record the names
and assertion text. Restore.

### V2 — mutation: prove `rowIntersectsSelection` is the right predicate

This is the subtle one; do not skip it. Temporarily change `already_selected` to
`selection_model.isSelected(index)` and run the same `-k "right_click"` selection.

Expected failure: `test_catalog_right_click_inside_the_existing_selection_preserves_it` fails,
because with `SelectItems` the clicked cell `(1, 0)` is not itself selected, so the handler
wrongly issues `ClearAndSelect` and destroys the user's selection of cell `(1, 2)`.

Then repeat with `selection_model.isRowSelected(index.row())` and confirm the same test fails
for the same reason. Record both. **If either mutation leaves all tests green, test 3 is not
actually pinning the predicate — fix the test before continuing.** Restore.

### V3 — mutation: prove the resize modes are load-bearing

Temporarily set column 2 back to `QHeaderView.ResizeMode.Stretch` and run:

```bash
./run.sh uv run pytest tests/test_catalog_dock.py -q
```

Expected failure: `test_catalog_all_columns_are_user_resizable` fails on the mode assertion and
on the `resizeSection` round-trip for column 2, and
`test_catalog_widening_the_dock_leaves_user_column_widths_alone` fails because Folder grows
again. Record both. Restore.

### V4 — negative control: full suite

Runs **after** V1-V3 so it cannot pass merely because nothing was exercised. Run each command
separately; do not chain with `&&` and do not pipe, so no failure is masked:

```bash
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
./run.sh uv run pytest
```

Record each exit status and the pytest pass/fail/skip tallies. Confirm
`tests/test_catalog_dock.py` now reports **24** tests (18 existing, one of which was rewritten
in place, plus 6 added). If the count differs, explain why. Note the Spark tier is deselected
by the default `-m 'not spark'` addopts and state the skip count.

Also confirm `test_all_tabular_views_allow_column_reordering`
(`tests/test_main_window.py:1329-1346`) still passes for the `catalog` parameter —
`setSectionsMovable(True)` must survive Task 4.

### V5 — observed-value check on column widths

Print real numbers rather than asserting a boolean. In a scratch script under
`/tmp/wherewolf/` (do not commit it), build a `CatalogDock` with three datasets at a 900 px
width and print, for each of the five columns: the resize mode, the initial section size, and
the size after `resizeSection(column, initial + 37)`.

Expected: all five modes `Interactive`; initial sizes `120, 220, 300, 90, 180`; every
post-resize size exactly `initial + 37`. Failure looks like any mode other than `Interactive`,
or a size that does not move. Paste the printed table into the session log, then delete the
script.

### Deferred and unverified

State these explicitly in the session log; do not claim them as verified:

- **On-screen confirmation is deferred.** Everything runs under `QT_QPA_PLATFORM=offscreen`
  (`tests/conftest.py:14`). That proves resize modes, section sizes, selection state and action
  enablement, but not that dragging a column divider with a real mouse feels right, nor that
  the context menu appears under the cursor. The user must confirm on a windowed session by
  launching `./run.sh uv run wherewolf-desktop`, dragging each of the five dividers, and
  right-clicking a dataset row other than the selected one.
- **The narrow-dock horizontal scrollbar is an accepted, unverified-on-screen consequence.**
  Default widths total 910 px; below that a scrollbar appears where columns previously squeezed.
  No test asserts scrollbar appearance.
- **Column widths still do not persist across restart.** Verified absent, explicitly out of
  scope, and unchanged by this plan.
- **Multi-selection batch actions remain broken.** Selecting several datasets and choosing
  Remove still removes only the anchored row. That is plan 3b and is *not* fixed here; the
  right-click anchoring in this plan is a prerequisite for it, not a partial delivery of it.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished dataset-columns-and-right-click
```

This writes:

```text
/tmp/wherewolf/dataset-columns-and-right-click_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer dataset-columns-and-right-click`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/dataset-columns-and-right-click-review-*.md
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
   scripts/orchestration/clear-finished dataset-columns-and-right-click
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
   git add docs/review/dataset-columns-and-right-click-review-*.md
   git commit -m "docs(review): record dataset-columns-and-right-click review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished dataset-columns-and-right-click
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer dataset-columns-and-right-click` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed dataset-columns-and-right-click
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize dataset-columns-and-right-click
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/dataset-columns-and-right-click_finalized
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
scripts/orchestration/finalize dataset-columns-and-right-click
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/dataset-columns-and-right-click_finished
/tmp/wherewolf/dataset-columns-and-right-click_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
