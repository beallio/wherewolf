# Plan: Desktop UX batch: history actions, cell selection, results auto-size, error surfacing, editor undo (desktop-ux-batch)

## Context

Six user-requested desktop changes, grouped into five areas. Every non-obvious
claim below was measured against this repo's installed Qt stack before the plan
was written; the measurements are restated so you can rebuild them rather than
trust them. All line numbers are as of `dev` at authoring time — re-locate by
symbol, not by line, once earlier tasks have shifted the files.

### Area 1 — `Ctrl+/` (Toggle Comment) does nothing

`SqlEditor._setup_actions` (`src/wherewolf/desktop/widgets/sql_editor.py:222-225`)
builds `_toggle_comment_action` with `QKeySequence("Ctrl+/")` and
`Qt.ShortcutContext.WidgetShortcut`, but the action is never added to a focusable
widget. `_setup_actions` only sets the caret line; `_setup_context_menu`
(`sql_editor.py:276`) is a bare `return`. The action reaches only the throwaway
`QMenu` built per right-click (`sql_editor.py:498`) and the window's Edit menu
(`main_window.py:1082`).

**The obvious fix — `self.addAction(...)` — does not work, and you must not use
it alone.** QScintilla accepts the `ShortcutOverride` event for Ctrl-modified
keys, so Qt's shortcut machinery never runs, under any context. Measured:

```text
plaintext  WidgetShortcut:        fired=True    <- control: plain QPlainTextEdit
qsci       WidgetShortcut:        fired=False
qsci       WidgetWithChildren:    fired=False
qsci       WindowShortcut:        fired=False
window-level QShortcut:           fired=False
keyPressEvent override:           fired=True    <- and the document is unchanged
```

The `keyPressEvent` route is the only one that works. The QAction stays — menu
activation ignores shortcut context and already works today, which is the
fastest way to confirm the diagnosis by hand.

The same dead-shortcut defect affects the editor's undo/redo/cut/copy/paste
actions (`sql_editor.py:197-220`), but Scintilla binds those keys natively and
`MainWindow` owns window-context duplicates (`main_window.py:1054-1075`), so
there is no user-visible symptom. **Leave them alone.** They are out of scope.

### Area 2 — undo is destroyed, not missing

QScintilla has a native undo stack and `_undo_action` is wired to it. But
`QsciScintilla.setText()` empties the undo buffer. Measured:

```text
undo available after normal edit: True
undo available after setText:     False
text after undo: '-- select 1\n'   <- undo did nothing
```

Three paths call `setText` and therefore discard the *entire* history, not just
their own change:

```text
src/wherewolf/desktop/widgets/sql_editor.py:137   the setText override itself
src/wherewolf/desktop/widgets/sql_editor.py:458   toggle_comment
src/wherewolf/desktop/widgets/sql_editor.py:486   replace_all
```

The override is reached from `_restore_history_query` (`main_window.py:1003`,
double-clicking a history row) and `_on_apply_query_order`
(`main_window.py:1016`, the results header's "Apply Order to Query", which also
runs the query immediately). The user's report is that double-clicking history
overwrites the editor with no way back — that is this bug.

A selection-based replacement inside one undo action fixes it. Measured:

```text
after restore:  'select * from history_record\n'
undo available: True
after one undo: 'select * from original\n'    <- single Ctrl+Z, exact restore
empty doc after undo: ''                      <- no phantom entry on an empty editor
```

`format_selection_or_statement` (`sql_editor.py:386-394`) and `CompletionAdapter`
(`completion_adapter.py:86-91`) already use this pattern correctly. Copy it.

### Area 3 — execution errors are easy to miss

`_on_query_result_ready` (`main_window.py:584-596`) sets a red-less label on the
Results page and appends to `MessagesPanel`, but the Messages tab is never
raised. The results `QTabWidget` is a local variable in `_build_central_area`
(`main_window.py:870`), so nothing else can reach it. `MessagesPanel._append_item`
(`messages_panel.py:89-91`) already stores severity in `Qt.ItemDataRole.UserRole`
but applies no colour.

### Area 4 — results columns do not size to content

`ResultTableView.auto_size_columns` (`result_table_view.py:137`) exists as a
manual header-menu action only. `PolarsTableModel.data` indexes the frame per
cell and the preview limit reaches 100 000 rows
(`settings_service.py:25`), so an unbounded `resizeColumnsToContents()` on a wide
frame is a visible stall. `QHeaderView.setResizeContentsPrecision` bounds the
row sample and must be set.

### Area 5 — history and catalog/schema selection

`HistoryDock` (`history_dock.py:37-90`) is a `QTreeWidget` with no context menu
and Qt's default single selection. `HistoryManager` (`storage/history.py`) has
`clear()` but no per-record delete; `_write_history` (`history.py:25-35`) is
already atomic via `os.replace`, so a delete method inherits that safety.

`CatalogDock` (`catalog_dock.py:59-60`) is `SelectRows` + `SingleSelection`.
`SchemaPanel` (`schema_panel.py:88-89`) is `SelectRows` + `ExtendedSelection`.

**The trap:** `CatalogDock._selected_entry` (`catalog_dock.py:163-176`) reads
`selectionModel().selectedRows()`, which returns an empty list as soon as rows
are no longer selected whole. Switching to `SelectItems` without changing that
method silently turns rename, remove, refresh, copy alias, copy path, insert
alias, and reveal into no-ops. Task 14 exists to prevent exactly that.

Selecting a row by its row number keeps working — `QHeaderView` handles it
independently of `SelectionBehavior`. Measured under `SelectItems` +
`ExtendedSelection`, a real click on the vertical header viewport:

```text
selected after real header click:   [(1, 0), (1, 1), (1, 2)]
selected after sectionClicked.emit: []
```

**Write header-click tests with `QTest.mouseClick` on
`verticalHeader().viewport()`. Emitting `sectionClicked` changes no selection and
produces a test that passes vacuously.**

### Decisions already made by the user

These were chosen before this plan was written. Do not substitute a different
shape; if you think one is wrong, say so in the session log and implement it as
written.

- **Save as SQL** writes **one concatenated `.sql` file** through a save-file
  dialog, records newest-first, each preceded by a `-- <timestamp>` comment line
  and separated by a blank line. Not one file per record.
- **History delete shows a confirmation dialog** naming the record count, because
  the delete is permanent. (The existing Clear History at `main_window.py:1235`
  has no confirmation; that inconsistency is accepted and out of scope.)
- **Results auto-size defaults to ON with a 300 px maximum column width.**
- **Undo work is editor-scoped only** — history restore, Apply Order to Query,
  Toggle Comment, Replace All. No `QUndoStack`, and no undo for catalog or
  history mutations.

### Explicitly out of scope

- Copy-to-clipboard (`Ctrl+C`) in the catalog view. Cell selection invites it,
  but the existing `serialize_table_widget_to_tsv`
  (`desktop/clipboard_serializers.py`) is `QTableWidget`-specific and the catalog
  is a model-backed `QTableView`. Note it in the session log for a separate plan.
- Undo for catalog remove/rename and history delete.
- The dead undo/redo/cut/copy/paste shortcuts described in Area 1.
- Making Clear History confirm.

**Slug used throughout this plan:** `desktop-ux-batch`

---

## Orchestration Contract

**Slug:** `desktop-ux-batch`

**Plan file:**

```text
docs/plans/2026-08-11_desktop-ux-batch.md
```

**Implementation branch:**

```text
feat/desktop-ux-batch
```

**Round-complete marker:**

```text
/tmp/wherewolf/desktop-ux-batch_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/desktop-ux-batch_finalized
```

**Review notes:**

```text
docs/review/desktop-ux-batch-review-*.md
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
git checkout -b feat/desktop-ux-batch
```

Commit this plan first:

```bash
git add docs/plans/2026-08-11_desktop-ux-batch.md
git commit -m "docs(plan): add desktop-ux-batch implementation plan"
```

---

## Implementation Tasks

Fifteen atomic tasks, in order. Each is one behaviour change, its own tests, its
own commit. TDD: write the failing test first, **record the actual failure output
in the session log**, then implement.

### Round boundaries — one task per round

This plan is reviewed task by task. A "round" in the orchestration contract above
means **exactly one task**, not the whole plan.

After finishing each task:

1. run the quality gates listed under `## Quality Gates`;
2. commit the task's code and tests;
3. run `scripts/orchestration/mark-finished desktop-ux-batch`;
4. exit cleanly and wait. Do not start the next task.

The orchestrator writes a review note per round. Fifteen tasks means at least
fifteen rounds. Do not batch tasks; a round containing two tasks' commits must be
split before it is marked finished.

**Review-note semantics — this overrides `## Approval Handling` below.**

This project runs the orchestrator in `final` approval mode
(`scripts/orchestration/lib.sh:91`, no override in `orchestration.conf` or
`orchestration.conf.local`), so **you will never receive a `STATUS: APPROVED`
note.** Do not wait for one, and do not run `scripts/orchestration/finalize`.
Integration is the orchestrator's job, performed after the last round.

Every review note you receive ends with `STATUS: CHANGES_REQUESTED`. Each note
states near the top whether the task just completed was accepted:

- **"Task N accepted — proceed to Task N+1"**: run
  `scripts/orchestration/clear-finished desktop-ux-batch`, commit the review note
  if it is not already committed, apply any additional findings, and begin the
  next task.
- **No acceptance line, or findings against the current task**: the task is not
  accepted. Fix it in place, re-run the gates, re-commit, re-mark the round. Do
  not advance.

If a note is ambiguous about which task it refers to, treat it as referring to the
task whose commits were in the round just marked finished, and say so in the
session log.

### Standing rules

- Every command that touches project tooling goes through `./run.sh`, per
  `CLAUDE.md` §5. Never invoke `uv`, `pytest`, `ruff`, or `ty` bare.
- Every test must assert **what the user sees or what a caller receives** — the
  text in a cell, the document contents after an undo, the file written to disk,
  the tab that is current. A test that asserts only that an attribute was
  assigned proves nothing.
- Qt tests run headless under the offscreen platform already configured in
  `tests/conftest.py:13`. Follow the existing fixture style in
  `tests/test_sql_editor.py`, `tests/test_catalog_dock.py`, and
  `tests/test_main_window.py`. Do not introduce a new Qt fixture style.
- Dialogs are tested by monkeypatching the symbol **where it is imported**, the
  pattern already used at `tests/test_catalog_dock.py:310` and
  `tests/test_main_window.py:418`. Never let a test open a real modal.
- Run `scripts/check_cache_budget.sh` after each task and record the byte count in
  the session log.
- Line numbers in this plan are from `dev` at authoring time. After the first few
  tasks they will have shifted; locate code by symbol name.

---

### Task 1 — Make `Ctrl+/` reach Toggle Comment

Add a `keyPressEvent` override to `SqlEditor`
(`src/wherewolf/desktop/widgets/sql_editor.py`). When the incoming key
combination matches `QKeySequence("Ctrl+/")`, trigger
`self._toggle_comment_action`, accept the event, and return; otherwise delegate to
`super().keyPressEvent(a0)`. Handle `a0 is None` — the rest of this codebase does
(`schema_panel.py:206`, `result_table_view.py:271`).

Store the sequence once as a module-level or class-level constant rather than
rebuilding it per keystroke; this runs on every key press.

Do **not** use `self.addAction(...)` as the fix — the Context section records the
measurement showing it does not fire on `QsciScintilla`. Adding it as well is
harmless but proves nothing; if you add it, do not claim it is what made the test
pass. Keep the existing `QAction`, its shortcut, and its `WidgetShortcut` context
so the Edit-menu entry and its shortcut hint are unchanged.

**Failing test first** (`tests/test_sql_editor.py`): build a `SqlEditor`, show it,
`QTest.qWaitForWindowExposed`, focus it, set text `select 1`, then

```python
QTest.keyClick(editor, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier)
```

Assert the document is now `-- select 1`. Under current code the text is
unchanged — record that exact red output. Add a second assertion that the
keystroke did not insert a stray `/` character, since that is the failure mode if
the event is accepted incorrectly.

Commit: `fix(editor): route Ctrl+/ to toggle comment`.

---

### Task 2 — Undoable whole-document replacement

Add to `SqlEditor`, next to the existing `setText` override
(`sql_editor.py:130-138`):

```python
def set_text_undoable(self, text: str) -> None:
    self.beginUndoAction()
    try:
        self.selectAll(True)
        self.replaceSelectedText(text)
    finally:
        self.endUndoAction()
    self.setScrollWidth(1)
```

The `setScrollWidth(1)` reset is the reason the `setText` override exists; the
undoable variant needs it for the same reason. Leave `setText` in place — it is
still correct for genuine document loads.

Then switch both call sites in `src/wherewolf/desktop/main_window.py`:

- `_restore_history_query` (`main_window.py:1003-1007`);
- `_on_apply_query_order` (`main_window.py:1009-1017`). Change only the text
  replacement. The `self._on_run_triggered()` that follows stays.

**Failing test first** (`tests/test_main_window.py`): set the editor to
`select * from original`, emit the history dock's `record_selected` with a record
whose `query` is `select * from history_record`, assert the editor shows the new
query **and** `editor.isUndoAvailable()` is `True`, then call `editor.undo()` once
and assert the editor is back to `select * from original`. Under current code
`isUndoAvailable()` is `False` and the undo is a no-op — record both.

Add the equivalent test for `_on_apply_query_order`.

Commit: `fix(editor): make history restore and apply-order undoable`.

---

### Task 3 — Make Toggle Comment undoable and selection-preserving

Rewrite `SqlEditor.toggle_comment` (`sql_editor.py:435-458`) to keep its current
per-line comment/uncomment logic — including the `-- ` / `--` prefix handling and
indentation preservation — but apply the edit through the selection API inside one
`beginUndoAction()`/`endUndoAction()` pair instead of `self.setText(...)`.

Requirements:

- one `Ctrl+Z` reverts the whole toggle, however many lines it covered;
- if there was a selection, the same line range is still selected afterwards, so
  pressing `Ctrl+/` twice round-trips;
- if there was no selection, the cursor stays on the same line.

`_selected_or_current_line_range` (`sql_editor.py:460-466`) already computes the
range; reuse it.

**Failing test first** (`tests/test_sql_editor.py`): select two lines, call
`toggle_comment()`, assert both lines are commented, assert `hasSelectedText()` is
still `True`, call `toggle_comment()` again and assert the document is byte-identical
to the original. Separately assert `isUndoAvailable()` is `True` after one toggle
and that a single `undo()` restores the original text. Under current code the
second toggle only affects the cursor line because the selection was destroyed —
record the actual post-toggle document.

The existing `test_sql_editor_toggle_comment_round_trips_selection`
(`tests/test_sql_editor.py:216`) must still pass unmodified. If it fails, you
changed the comment semantics; fix the implementation, not that test.

Commit: `fix(editor): make toggle comment undoable and keep the selection`.

---

### Task 4 — Make Replace All undoable

`SqlEditor.replace_all` (`sql_editor.py:480-487`) calls `setText`. Route it
through `set_text_undoable` from Task 2, preserving the existing return value
(the count of replacements) and the early return when nothing changes.

**Failing test first** (`tests/test_sql_editor.py`): set text containing two
occurrences, type a character so a normal edit exists in the undo buffer, call
`replace_all`, assert the returned count and the new text, then assert one
`undo()` restores the pre-replace text. Under current code `isUndoAvailable()` is
`False` after the call — record it.

Commit: `fix(editor): make replace all undoable`.

---

### Task 5 — Colour message severities

Add a severity-to-colour helper to `src/wherewolf/desktop/theming.py`, exported
through `__all__`, returning a `QColor` for `"error"`, `"warning"`, and `"info"`
in both light and dark modes. Errors are red in both; pick shades that meet
readable contrast against the `Base` colours already defined at
`theming.py:56-78` (`#1e1e1e` dark, `#ffffff` light) — a single red will fail one
of them.

Apply it in `MessagesPanel._append_item` (`messages_panel.py:89-91`) via
`item.setForeground(...)`. Resolve light vs dark from the widget's own palette
rather than adding a settings dependency — `ResultTableView.__init__`
(`result_table_view.py:32-39`) already establishes that idiom.

Existing behaviour that must not change: `message_at`
(`messages_panel.py:80-87`) still returns `(text, severity)`, and the severity
still lives in `Qt.ItemDataRole.UserRole`.

**Failing test first** (`tests/test_messages_panel.py`): add an error message and
assert the list item's `foreground().color()` is the expected error colour and is
**different** from the colour of an `info` message added to the same panel.
Asserting only that a foreground was set would pass against a black default —
assert the actual difference.

Commit: `feat(messages): colour message severities`.

---

### Task 6 — Raise the Messages tab on execution failure

Keep a reference to the results `QTabWidget` built in `_build_central_area`
(`main_window.py:870`) — assign it to `self` alongside the other widgets there.
In `_on_query_result_ready`, inside the existing
`if result.status is ExecutionStatus.FAILED:` branch (`main_window.py:584-591`),
make the Messages panel the current tab.

Only execution failures raise the tab. `_on_editor_diagnostics`
(`main_window.py:1192-1196`) also feeds the panel while the user types and must
**not** steal the tab; leave it untouched.

**Failing test first** (`tests/test_main_window.py`): with the Results tab
current, deliver a `FAILED` `QueryResult` through the same path the existing
result tests use, and assert the tab widget's `currentWidget()` is
`window.messages_panel`. Then deliver a `SUCCEEDED` result while the Results tab
is current and assert the current tab did **not** change — without this second
assertion the feature could unconditionally switch tabs and still pass. Add a
third: emit editor diagnostics and assert the tab does not change.

Commit: `feat(messages): raise the messages tab on execution failure`.

---

### Task 7 — Persist the auto-size preferences

Add two settings to `src/wherewolf/services/settings_service.py`, following the
existing key/property/restore/save quartet exactly (`preview_limit` at
`settings_service.py:66`, `130`, `225-239` is the closest model because it
clamps):

- `auto_size_columns`: bool, default `True`;
- `auto_size_max_width`: int pixels, default `300`, clamped on save and validated
  on restore to `50..2000`. Follow `restore_preview_limit`'s pattern of returning
  the default when the stored value is out of range, the wrong type, or a `bool`.

Add the constants next to the existing `DEFAULT_*` block (`settings_service.py:18-33`).

**Failing test first** (`tests/test_settings_service.py`): round-trip both
settings through a `QSettings` instance; assert an out-of-range width (`5` and
`9999`) restores as `300`, that a `True` stored in the width key restores as
`300` rather than `1`, and that the defaults on a fresh `QSettings` are `True`
and `300`.

Commit: `feat(settings): persist result column auto-size preferences`.

---

### Task 8 — Clamped auto-size in the results view

In `src/wherewolf/desktop/widgets/result_table_view.py`:

- add a method that accepts the enabled flag and the maximum width and stores
  them on the view (default them to `True` / `300` so a view constructed without
  the call behaves like the shipped default);
- change `auto_size_columns` (`result_table_view.py:137-138`) to resize to
  contents and then clamp every visible column to the stored maximum;
- call it from `set_frame` (`result_table_view.py:54-62`) after the model is
  populated, only when the flag is on;
- set `setResizeContentsPrecision` on the horizontal header to a bounded sample
  (200 rows) in `__init__`, so a 100 000-row preview does not stall the resize.

The header-menu "Auto-size Columns" action (`result_table_view.py:235`) keeps
working and now clamps too — that is intended.

**Failing test first** (`tests/test_result_table_view.py`): build a frame with one
column whose values are far wider than the maximum and one narrow column, call
`set_frame`, and assert the wide column's `columnWidth` is exactly the maximum
while the narrow column's is strictly less. Then set the flag off, call
`set_frame` again with a fresh view, and assert the wide column is **not**
clamped — without that second case a hardcoded clamp would pass.

Under current code `set_frame` never resizes, so the wide column sits at the
default section size; record it.

Commit: `feat(results): auto-size result columns with a width cap`.

---

### Task 9 — Expose auto-size in Preferences

In `PreferencesDialog` (`main_window.py:124-164`) add, following the existing
rows:

- a `QCheckBox` for auto-size, initialised from the settings service;
- a `QSpinBox` for the maximum width, range `50..2000`, initialised from the
  settings service, labelled with its unit (px).

Persist both in `_apply_preferences` (`main_window.py:1176-1184`) and push the
new values to `self.result_table_view` through the Task 8 method. Apply the
stored values at startup in `_restore_state` (`main_window.py:1203-1219`) so a
restart honours them.

**Failing test first** (`tests/test_main_window.py`): follow
`test_main_window_preferences_persist_and_change_editor_font`
(`tests/test_main_window.py:777`), including its `_configure_qsettings_path`
helper and its `window.preferences_action.trigger()` /
`window.preferences_dialog` access — open the dialog, set the checkbox off and the
width to `150`, accept, and assert (a) the settings service returns the new
values and (b) a subsequently delivered result frame is not auto-sized. Then
construct a fresh `MainWindow` against the same `QSettings` and assert the
restored view carries the width `150` — this is the assertion that catches a
missing `_restore_state` wiring.

Commit: `feat(preferences): expose result auto-size flag and max width`.

---

### Task 10 — Delete history records by id

Add a delete method to `HistoryManager` (`src/wherewolf/storage/history.py`)
taking an iterable of record ids and removing every matching record. Build the
survivor list from `get_all()` so the v1→v2 migration at `history.py:126-135` is
respected, and write through `_write_history` so the atomic `os.replace` applies.

Return the number of records actually removed. Unknown ids are ignored, not an
error. An empty iterable must not rewrite the file.

**Failing test first** (`tests/test_history.py`): seed three entries, delete the
middle one by id, assert `get_all()` returns the other two **in their original
order**, assert the return value is `1`, and assert `get_by_id` on the deleted id
returns `None`. Add a case deleting two ids at once, a case with an unknown id
(returns `0`, file unchanged), and a case proving a legacy v1 entry survives the
delete of a different record with its migrated id intact.

Commit: `feat(history): delete history records by id`.

---

### Task 11 — Serialise history records to SQL text

Add a pure function to `src/wherewolf/services/` (new module, e.g.
`history_sql_export.py`) that takes an ordered sequence of history records and
returns the `.sql` file body decided by the user: newest-first, each record
preceded by a `-- <timestamp>` comment line, records separated by a blank line,
and the text ending in exactly one trailing newline.

No Qt, no filesystem access, no dialogs in this module. Export it through
`src/wherewolf/services/__init__.py` alongside the existing services.

Records whose `query` is missing or not a string are skipped. A record whose
query already ends in a newline must not produce a double blank line.

**Failing test first** (new `tests/test_history_sql_export.py`): assert the exact
full string for two records — not a substring or a line count. Add cases for a
single record, an empty sequence (returns `""`), a query with trailing whitespace,
and a query containing an embedded `--` comment (must pass through unchanged).

Commit: `feat(history): serialise history records to SQL text`.

---

### Task 12 — History multi-select, context menu, and delete

In `src/wherewolf/desktop/widgets/history_dock.py`:

- set `ExtendedSelection` on `self.history_table` so shift and ctrl select
  multiple rows;
- set `Qt.ContextMenuPolicy.CustomContextMenu` and connect a handler, following
  the structure of `CatalogDock._on_context_menu` (`catalog_dock.py:178-203`) —
  build the `QAction`s once in `__init__`, enable/disable them per invocation,
  and pop the menu at the viewport-mapped position;
- add a Delete action that collects the selected records' ids (stored in
  `Qt.ItemDataRole.UserRole` at `history_dock.py:79`), shows a `QMessageBox`
  confirmation naming the count, and on confirmation calls the Task 10 delete
  method and then `self.refresh()`;
- right-clicking a row that is not part of the current selection selects that row
  first; right-clicking inside an existing multi-row selection preserves it.

Cancelling the dialog must delete nothing.

**Failing test first** (`tests/test_history_dock.py`): seed three records, select
two, monkeypatch the `QMessageBox` question in the `history_dock` namespace to
return the Yes button, trigger the delete action, and assert the manager holds
only the third record **and** the tree shows one row. Add the cancel case
asserting all three survive, and a case asserting a right-click on an unselected
row reduces the selection to that row.

Commit: `feat(history): multi-select and delete history records`.

---

### Task 13 — Save selected history records as SQL

Add a "Save as SQL…" action to the history context menu from Task 12. It serialises
the selected records with the Task 11 function and writes the result to a path the
user chooses.

Keep the dialog out of the widget: have `HistoryDock` emit a signal carrying the
selected records, and let `MainWindow` own the file dialog and the write, the way
export already works (`main_window.py:634`, `685`). Add a save-path method to
`QtFileDialogService` and `FakeFileDialogService`
(`src/wherewolf/desktop/dialogs/file_dialog_service.py`) using
`QFileDialog.getSaveFileName` with a `*.sql` filter, mirroring `choose_export_path`
(`file_dialog_service.py:79-89`) — including its comment about not suppressing the
overwrite prompt. Append `.sql` when the chosen name has no suffix.

Write the file through `write_atomically`
(`src/wherewolf/services/export_destination.py:34`), already re-exported from
`wherewolf.services`, rather than a bare `open()` — the repo does not write user
files non-atomically anywhere else.

A cancelled dialog writes nothing. Report a write failure through the existing
`_show_status` path rather than raising.

**Failing test first** (`tests/test_main_window.py`): drive a `MainWindow` with a
`FakeFileDialogService` pointed at a `tmp_path` file, select two history records,
trigger the action, and assert the file's contents equal the Task 11 function's
output for those records. Add the cancelled case asserting no file is created.

Commit: `feat(history): save selected history records as SQL`.

---

### Task 14 — Cell selection in the dataset catalog

In `CatalogDock.__init__` (`catalog_dock.py:58-60`) switch the view to
`SelectionBehavior.SelectItems` and `SelectionMode.ExtendedSelection`.

**In the same commit**, fix `_selected_entry` (`catalog_dock.py:163-176`) so the
context-menu actions still resolve a row under cell selection — derive the row
from the current index, and return `None` only when there is genuinely no valid
current row. Do not change the actions themselves.

Leave the Task-2-era column sizing alone: the `Stretch` mode on the File column
(`catalog_dock.py:55`) and `ElideMiddle` (`catalog_dock.py:50`) stay exactly as
they are. Keep `setEditTriggers(DoubleClicked)` — alias renaming through the model
must still work.

**Failing test first** (`tests/test_catalog_dock.py`), three assertions, all of
which must be present:

1. clicking a single cell in the File column selects that cell only —
   `selectionModel().selectedIndexes()` has length 1;
2. with only that one cell selected, `Remove` still removes the right entry, and
   `Copy Alias` still copies the right alias — this is the regression guard and it
   fails hard if `_selected_entry` was not updated;
3. clicking the vertical header for row 1 selects that whole row — use
   `QTest.mouseClick` on `verticalHeader().viewport()`, **not**
   `sectionClicked.emit`, per the measurement in `## Context`.

Commit: `feat(catalog): select individual catalog cells`.

---

### Task 15 — Cell selection in the schema panel

In `SchemaPanel.__init__` (`schema_panel.py:88`) switch to
`SelectionBehavior.SelectItems`, keeping the existing `ExtendedSelection`.

Then fix `_on_context_menu_requested` (`schema_panel.py:197-204`), which calls
`selectRow(index.row())` unconditionally and would wipe a multi-cell selection on
right-click: select the clicked cell only when it is not already part of the
current selection.

Check `copy_selection` (`schema_panel.py:213-219`) against a non-contiguous cell
selection before you finish. `serialize_table_widget_to_tsv`
(`desktop/clipboard_serializers.py`) was written against row selections; if it
produces misaligned rows for scattered cells, **stop and report it in the session
log rather than rewriting the serializer** — that is a separate plan.

`get_selected_column_names` (`schema_panel.py:171-175`) already derives rows from
`selectedIndexes()`, so it keeps working; selecting a single `Type` cell now
inserts that row's column name, which is the intended behaviour.

**Failing test first** (`tests/test_schema_panel.py`): populate the panel, click a
single `Type` cell, and assert exactly one index is selected. Assert
`get_selected_column_names()` still returns that row's column name. Then select
cells in two different rows, right-click inside the selection, and assert both
rows are still selected after the menu is built. Finally assert a vertical-header
click selects the whole row, again with `QTest.mouseClick` on the header viewport.

Commit: `feat(schema): select individual schema cells`.

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

Standards: `references/verification-standards.md` in the
`orchestration-plan-author` skill. Report **output**, not conclusions — paste the
tallies and the failure text, never "confirmed passing".

Run this section on the final round, after Task 15's tests are green. V1–V7
deliberately break the implementation to prove the gates can fail; V8 is the
negative control and must run last.

Every mutation is reverted with `git checkout -- <file>`, which is safe only
because each task is already committed. Before starting, confirm that:

```bash
set -o pipefail
git status --porcelain
```

prints nothing. If it prints anything, stop — a mutation revert would destroy
uncommitted work.

### V1 — Remove the key route (Task 1)

Delete the `keyPressEvent` override from
`src/wherewolf/desktop/widgets/sql_editor.py`, then:

```bash
set -o pipefail
./run.sh uv run pytest tests/test_sql_editor.py -x
status=$?
git checkout -- src/wherewolf/desktop/widgets/sql_editor.py
echo "V1 pytest exit: $status"
```

Expected: non-zero exit, with the failure showing the document still reading
`select 1` after the keystroke. Record the assertion message verbatim. Exit 0
means the Task 1 test is not actually sending a key event — fix the test, not the
mutation.

### V2 — Restore the destructive `setText` (Task 2)

In `src/wherewolf/desktop/main_window.py`, change `_restore_history_query` back to
`self.editor.setText(query)`, then run `tests/test_main_window.py -x` with the
same command block shape as V1. Expected: non-zero exit, with the failure showing
`isUndoAvailable()` as `False` or the post-undo text still equal to the restored
query. Revert and record the message.

### V3 — Restore `setText` in toggle comment (Task 3)

Change `toggle_comment` back to `self.setText("".join(lines))`, then run
`tests/test_sql_editor.py -x`. Expected: non-zero exit, and the failure is about
the lost selection or the unavailable undo — **not** about the comment characters,
which this mutation does not change. Record which assertion fired. If the failure
is about comment text instead, the Task 3 test is testing the wrong thing.

### V4 — Remove the width clamp (Task 8)

Delete the clamping step from `ResultTableView.auto_size_columns`, leaving the
`resizeColumnsToContents()` call, then run `tests/test_result_table_view.py -x`.
Expected: non-zero exit, and the failure prints the unclamped column width as
greater than the configured maximum. Record both numbers. Exit 0 means the test's
wide column is not actually wider than the cap — widen the fixture.

### V5 — Remove the tab switch (Task 6)

Delete the line that makes the Messages panel current in `_on_query_result_ready`,
then run `tests/test_main_window.py -x`. Expected: non-zero exit naming the
Results page as `currentWidget()`. Revert and record.

### V6 — Restore the `selectedRows()` regression (Task 14)

This is the most important mutation in this plan. In
`src/wherewolf/desktop/widgets/catalog_dock.py`, revert `_selected_entry` to its
original `selectionModel().selectedRows()` body while **leaving**
`SelectItems` in place, then run `tests/test_catalog_dock.py -x`.

Expected: non-zero exit, and the failure is the Remove/Copy Alias assertion from
Task 14 — proving that test would have caught the silent no-op. Record the message.
An exit status of 0 means Task 14's regression guard is decoration and the catalog
context menu can break unnoticed; fix the test before proceeding.

### V7 — Prove the header-click assertions are live (Tasks 14, 15)

The measurement in `## Context` shows `sectionClicked.emit(row)` changes no
selection. Temporarily replace the `QTest.mouseClick` call in the Task 14
header-click test with `verticalHeader().sectionClicked.emit(1)` and re-run
`tests/test_catalog_dock.py -x`.

Expected: the test **fails**, because no selection occurs. Record the failure,
then restore the test with `git checkout -- tests/test_catalog_dock.py`. If it
passes, the test is not asserting on selection state at all and both Task 14 and
Task 15 header assertions are vacuous — say so in the session log and fix them.

### V8 — Negative control (runs last)

With every mutation reverted and the tree clean:

```bash
set -o pipefail
git status --porcelain
./run.sh uv run ruff check .
./run.sh uv run ty check src/
./run.sh uv run pytest
scripts/check_cache_budget.sh
```

Record: the `git status --porcelain` output (must be empty), the ty result line,
the pytest `passed`/`failed`/`error` tallies, and the cache byte count. This step
passes only if the implementation works, and it runs after V1–V7 so it cannot
pass merely because nothing was exercised.

### V9 — Repository cleanliness

```bash
set -o pipefail
git ls-files --others --exclude-standard
find . -path ./.git -prune -o -name '__pycache__' -print -o -name '.pytest_cache' -print
```

Expected: no untracked files, and no cache directories inside the repository per
`CLAUDE.md` §5. Paste both outputs. Non-empty output is a failure, not a note.

### Explicitly deferred / not verified

State each of these in the session log; an unstated gap reads as a covered one.

- **No GUI was launched.** Every check is headless under the offscreen platform.
  Nobody has looked at the running window. The user must confirm by hand: that
  `Ctrl+/` works with their real keyboard layout (layouts where `/` requires a
  modifier are not covered by `QTest.keyClick`, which synthesises the key
  directly); that the error red is readable in both themes; and that the 300 px
  cap feels right on their own result sets.
- **The `ShortcutOverride` behaviour is version-specific.** The measurement that
  `addAction` does not work was taken against the currently installed QScintilla.
  A future version could change it. The `keyPressEvent` route does not depend on
  that behaviour, which is why it was chosen.
- **Auto-size cost is not benchmarked.** `setResizeContentsPrecision(200)` bounds
  the sample by construction, but no test measures wall-clock time on a
  100 000-row preview. If the user reports a stall after a large query, that is
  the first thing to measure.
- **Non-contiguous clipboard output is inspected, not fixed.** Task 15 asks you to
  check `serialize_table_widget_to_tsv` against scattered cell selections and
  report what you find. If it misaligns, the report is the deliverable; the fix is
  a separate plan.
- **Catalog `Ctrl+C` does not exist.** Cell selection invites it and this plan does
  not add it.
- **History delete has no undo.** The confirmation dialog is the only guard, by
  the user's decision. Records deleted through this menu are gone.
- **Only DuckDB result frames were exercised for auto-size.** Spark-engine result
  frames go through the same `PolarsTableModel`, but no test drives that path.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished desktop-ux-batch
```

This writes:

```text
/tmp/wherewolf/desktop-ux-batch_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer desktop-ux-batch`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/desktop-ux-batch-review-*.md
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
   scripts/orchestration/clear-finished desktop-ux-batch
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
   git add docs/review/desktop-ux-batch-review-*.md
   git commit -m "docs(review): record desktop-ux-batch review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished desktop-ux-batch
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer desktop-ux-batch` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed desktop-ux-batch
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize desktop-ux-batch
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/desktop-ux-batch_finalized
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
scripts/orchestration/finalize desktop-ux-batch
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/desktop-ux-batch_finished
/tmp/wherewolf/desktop-ux-batch_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
