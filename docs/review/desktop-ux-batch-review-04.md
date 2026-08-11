# Review — desktop-ux-batch (round 04)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `f874482 fix(editor): keep toggle selection on selected lines`

## Verdict

**Task 3 accepted — proceed to Task 4.**

The round-03 defect is fixed. The clamp was applied as prescribed and the
regression test covers the case that exposed it.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      505 passed, 7 deselected in 13.07s   (502 before Task 3 — three new tests)
git status:  clean (empty --porcelain)
```

### Independent verification performed

1. **Mutation — the new test catches the original bug.** Restored the
   `self.lineLength(line_end - 1)` call and re-ran the focused test:

   ```text
   FAILED tests/test_sql_editor.py::test_sql_editor_toggle_comment_round_trips_mid_document_selected_lines
   1 failed, 27 deselected
   MUTATION exit: 1
   ```

   Reverted. The test fails on the pre-fix code, which is what round 03 required.

2. **Edge cases beyond the required test**, driven against the real `SqlEditor`:

   ```text
   trailing newline doc   round_trip=True  first='-- select 1;\n-- select 2;\n'
   single line            round_trip=True  first='-- select 1;'
   indented block         round_trip=True  first='  -- select 1;\n  -- select 2;\nselect 3;'
   ```

   A document ending in a newline, a single-line document, and an indented block
   all round-trip cleanly, and indentation is preserved ahead of the `-- `
   marker. `rstrip("\r\n")` also covers CRLF documents by construction.

## Required changes

None for Task 3.

## Next

Begin **Task 4 — Make Replace All undoable**. `replace_all` should route through
`set_text_undoable` from Task 2; preserve both its return value (the count of
replacements) and its early return when nothing changed. The plan's test asks you
to make a normal edit first so the undo buffer is non-empty before the call.

STATUS: CHANGES_REQUESTED
