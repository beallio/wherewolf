# Review — desktop-ux-batch (round 18)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `504e586 feat(catalog): select individual catalog cells`

## Verdict

**Task 14 accepted — proceed to Task 15.**

`SelectItems` + `ExtendedSelection` on the catalog view, with `_selected_entry`
fixed **in the same commit** as the plan demanded. `ElideMiddle` and the `Stretch`
mode on the File column are untouched.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      543 passed, 7 deselected in 14.03s   (541 before this task — two new tests)
git status:  clean (empty --porcelain)
```

### Independent verification performed

1. **The mutation this task exists for.** Reverted `_selected_entry` to
   `selectionModel().selectedRows()` while leaving `SelectItems` in place — the
   exact silent regression the plan warned about:

   ```text
   FAILED tests/test_catalog_dock.py::test_catalog_cell_selection_keeps_context_actions_on_the_clicked_entry
   1 failed, 17 passed
   ```

   The regression guard bites. Had it not, rename/remove/refresh/copy/insert/
   reveal could have become no-ops with every test green. Reverted.

2. **Alias editing still works under cell selection**, which `SelectItems` could
   plausibly have disturbed given `setEditTriggers(DoubleClicked)`:

   ```text
   alias edit via model: True -> renamed_alias
   ```

3. **The vertical-header test uses a real `QTest.mouseClick`** on the header
   viewport and asserts all four columns of row 1 are selected. It is not the
   `sectionClicked.emit` no-op the plan warned about.

## Non-blocking observation — a behaviour change worth knowing about

`currentIndex()` stays valid after the selection is emptied, so `_selected_entry`
now resolves an entry when **nothing is selected**:

```text
after click       : selected = 1 | _selected_entry -> b
after clearSelect : selected = 0 | _selected_entry -> b
   (the old selectedRows() behaviour returned None here, disabling the actions)
```

Reaching this state takes a deliberate Ctrl+click to deselect, Qt still paints the
focus rectangle on the current cell, and `Remove` only drops the catalog entry —
it does not touch the file on disk. This is also exactly what the plan
instructed ("derive the row from the current index, and return `None` only when
there is genuinely no valid current row"), so it is **not** a defect against the
plan and no change is required.

Record it in the session log. If it ever bothers a user, the targeted fix is to
gate `_remove_action` on a non-empty selection rather than on `_selected_entry`.

## Next

Begin **Task 15 — Cell selection in the schema panel**, the last implementation
task. Three things:

- switch `SelectionBehavior` to `SelectItems`, keeping `ExtendedSelection`;
- fix `_on_context_menu_requested`, which calls `selectRow(index.row())`
  unconditionally and would wipe a multi-cell selection on right-click — select
  the clicked cell only when it is not already part of the selection;
- check `copy_selection` / `serialize_table_widget_to_tsv` against a
  **non-contiguous** cell selection. The plan is explicit: if it misaligns,
  **report it in the session log rather than rewriting the serializer**. The
  report is the deliverable there, not a fix.

Note from round 15: Qt's own `mousePressEvent` already drives some right-click
selection behaviour, so verify your context-menu fix is doing the work rather
than passing on Qt's default.

STATUS: CHANGES_REQUESTED
