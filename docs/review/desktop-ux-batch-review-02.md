# Review — desktop-ux-batch (round 02)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `2a8a0f1 fix(editor): make history restore and apply-order undoable`

## Verdict

**Task 2 accepted — proceed to Task 3.**

`set_text_undoable` is exactly the shape the plan specified: `beginUndoAction()`,
`selectAll(True)`, `replaceSelectedText(text)`, `endUndoAction()` in a `finally`,
then `setScrollWidth(1)`. The original `setText` override is left in place for
genuine document loads. Both call sites were switched, and
`_on_apply_query_order` still calls `_on_run_triggered()` afterwards as required.

Test construction is sound in a way worth calling out: both tests seed the editor
with `setText`, which empties the undo buffer. That makes the subsequent
`isUndoAvailable()` assertion meaningful rather than incidental — it can only be
`True` because of the code under test.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      502 passed, 7 deselected in 13.35s   (500 before this task — two new tests)
git status:  clean (empty --porcelain)
```

### Independent verification performed

1. **Mutation — the tests are not vacuous.** Reverted `_restore_history_query` to
   `self.editor.setText(query)` and re-ran the two new tests:

   ```text
   FAILED tests/test_main_window.py::test_history_record_restore_replaces_editor_text_in_one_undo_action
   1 failed, 1 passed, 92 deselected
   MUTATION-A exit: 1
   ```

   The history test fails and the apply-order test still passes, which correctly
   localises the mutation. Reverted.

2. **Empty-editor edge case — not covered by your tests, checked by hand.**
   Calling `set_text_undoable` on a freshly constructed editor:

   ```text
   empty-start text: 'select 1'  undo_available: True
   after undo: ''
   cursor after restore: (0, 0)
   ```

   No phantom undo entry, no cursor regression. This is the state the app is in
   at startup before any query is typed, so it is worth knowing it behaves. No
   change requested.

## Required changes

None for Task 2.

## Non-blocking observations

- `set_text_undoable` is now load-bearing for Task 4 (`replace_all` routes
  through it) and is adjacent to Task 3. Do not change its signature or its
  `setScrollWidth(1)` tail in those tasks without saying so explicitly in the
  session log.
- Neither test asserts the caret position after a restore. Behaviour differs
  subtly from the old `setText` path, but measured above it lands at `(0, 0)`,
  which matches the previous behaviour. Not worth a test.

## Next

Begin **Task 3 — Make Toggle Comment undoable and selection-preserving**. Two
plan requirements are easy to miss: the same line range must still be selected
after the toggle so `Ctrl+/` round-trips, and the pre-existing
`test_sql_editor_toggle_comment_round_trips_selection` must pass **unmodified**.
If that existing test fails, the comment semantics changed — fix the
implementation, not the test.

STATUS: CHANGES_REQUESTED
