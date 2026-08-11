# Review — desktop-ux-batch (round 01)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `b3017c8 fix(editor): route Ctrl+/ to toggle comment`

## Verdict

**Task 1 accepted — proceed to Task 2.**

The implementation matches the plan: a `keyPressEvent` override on `SqlEditor`
triggers the existing `QAction`, accepts the event, and delegates everything else
to the base class. The sequence is hoisted to a module-level constant. The
`QAction`, its shortcut, and its `WidgetShortcut` context are untouched, so the
Edit-menu entry and its shortcut hint still render. `addAction` was correctly not
used as the fix.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:            500 passed, 7 deselected in 13.21s   (baseline was 499 — exactly one new test)
git status:        clean (empty --porcelain)
ty (src/):         All checks passed
```

### Independent verification performed

1. **Mutation — the test is not vacuous.** Removed the `keyPressEvent` override
   and re-ran the focused test:

   ```text
   E         ? ---
   E         + select 1
   tests/test_sql_editor.py:246: AssertionError
   1 failed, 24 deselected
   MUTATION pytest exit: 1
   ```

   The test fails for the right reason — the document is unchanged after the
   keystroke — and passes only with the override present. Reverted.

2. **The two `ty: ignore[no-matching-overload]` suppressions are warranted, not
   noise.** Stripped both and re-ran `ty`:

   ```text
   Found 2 diagnostics
   ty-without-suppressions exit: 1
   ```

   The diagnostics confirm the session log's claim: PyQt's `QTest` stubs model
   the static helpers as instance methods. `QTest` appears nowhere else in
   `tests/`, so there was no existing precedent to follow. Reverted.

3. **Module-level `QKeySequence` is import-safe.** `_TOGGLE_COMMENT_SHORTCUT` is
   constructed at import time, before any `QApplication` exists. Verified that
   importing the module standalone works and parses correctly:

   ```text
   import ok, seq = Ctrl+/
   ```

   This matters because `cli.py` imports this package outside a GUI session.

## Required changes

None for Task 1.

## Non-blocking observations

Do **not** address these in a new round; they are recorded for the audit trail
and may be folded into a later task only if you are already editing the same
lines.

- `if e is None: return` swallows the event rather than delegating to
  `super().keyPressEvent(e)`. The stub types `e` as non-optional so this is
  unreachable today, and the rest of the codebase is defensive the same way
  (`schema_panel.py`, `result_table_view.py`). Harmless as written.
- `QKeySequence(e.keyCombination())` allocates on **every** keystroke, in an
  editor's hottest path. The plan's "store the sequence once" instruction was
  about the constant, which you did hoist, so this is compliant. If Task 3 has
  you back in this method, comparing `e.key()` and `e.modifiers()` directly would
  remove the per-keystroke allocation.
- `assert "/" not in editor.text()` is implied by the preceding
  `assert editor.text() == "-- select 1"`. It costs nothing and documents intent;
  keep it.

## Next

Begin **Task 2 — Undoable whole-document replacement**. Note the plan's warning
that `setScrollWidth(1)` must be preserved in `set_text_undoable`, and that both
call sites (`_restore_history_query` and `_on_apply_query_order`) change while
`_on_run_triggered()` in the latter stays.

STATUS: CHANGES_REQUESTED
