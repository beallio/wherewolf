# Review — desktop-ux-batch (round 15)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `b2dce7d feat(history): multi-select and delete history records`

## Verdict

**Task 12 accepted — proceed to Task 13.**

`ExtendedSelection`, a custom context menu built once in `__init__`, a
count-naming confirmation, and deletion through `HistoryManager.delete_records`
followed by `refresh()`. The tests drive real `qtbot.mouseClick` calls with a
`ControlModifier` for the multi-select, which is the right level to test this at.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      532 passed, 7 deselected in 13.75s   (529 before this task — three new tests)
git status:  clean (empty --porcelain)
```

### Independent verification performed

```text
A: delete without confirming                    -> FAILED (cancelled-delete test)
B: remove the "reduce selection to clicked row" -> 8 passed
C: revert ExtendedSelection to SingleSelection  -> FAILED (context-click test)
```

All reverted. A and C confirm the confirmation dialog and the multi-select mode
are both covered.

## On mutation B — a finding, not a required change

Deleting this block from `_on_context_menu` changes nothing observable:

```python
        if item is not None and not item.isSelected():
            self.history_table.clearSelection()
            item.setSelected(True)
            self.history_table.setCurrentItem(item)
```

`QAbstractItemView::mousePressEvent` already handles right-button presses: it
selects the item under the cursor when that item is unselected, and leaves an
existing multi-row selection alone when the click lands inside it. Both branches
of the plan's requirement are Qt's native behaviour, so
`test_history_dock_context_click_preserves_selected_rows_or_selects_clicked_row`
passes with or without your code — it is exercising Qt, not this widget.

**Keep the block.** It states the intent explicitly and costs nothing, and it
also covers the keyboard-menu-key path where no mouse press occurs. But record in
the session log that it is not covered by any test, so nobody later mistakes the
green test for proof that this code runs. Do not add a test that asserts the
block exists — that would test shape, not behaviour.

## Non-blocking observations

- `menu = QMenu(self)` is created per invocation and parented to the dock, so
  menus accumulate as children over a long session. `CatalogDock._on_context_menu`
  has the identical pattern, so this is consistent with the codebase rather than a
  new problem. Out of scope here.
- `monkeypatch.setattr(history_dock.QMessageBox, "question", ...)` patches the
  attribute on the real `QMessageBox` class rather than on the module, so it is
  process-wide for the duration of the test. `monkeypatch` restores it, and the
  preceding `setattr(history_dock, "QMessageBox", QMessageBox, raising=False)`
  makes the intent explicit. Acceptable; patching a module-local alias would be
  tighter.
- `selectedItems()` on a two-column `QTreeWidget` returns one item per row, not
  per cell, so `_selected_record_ids` cannot double-count. Verified by the
  two-record delete asserting exactly one survivor.

## Next

Begin **Task 13 — Save selected history records as SQL**. Design constraints from
the plan: the dialog stays **out** of the widget — `HistoryDock` emits a signal
carrying the selected records and `MainWindow` owns the dialog and the write;
add the save-path method to **both** `QtFileDialogService` and
`FakeFileDialogService`; append `.sql` when the chosen name has no suffix; write
through `write_atomically` (`services/export_destination.py:34`); a cancelled
dialog writes nothing; report write failures through `_show_status` rather than
raising.

STATUS: CHANGES_REQUESTED
