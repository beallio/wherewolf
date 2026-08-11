# Review — desktop-ux-batch (round 03)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `366c2e1 fix(editor): make toggle comment undoable and keep the selection`

## Verdict

**Task 3 is NOT accepted.** The undo half is correct. The selection-restore half
has a real defect: a round trip corrupts a line the user never selected whenever
the selection ends anywhere other than the final line of the document.

Do not advance to Task 4. Fix this in place, re-run the gates, re-commit, and
re-mark the round.

## The defect

`self.lineLength(line)` returns the line length **including its EOL characters**.
For any line but the last, that is one (or two) more than the visible text. The
restore therefore selects past the end of the line and Scintilla normalises the
selection onto the following line.

Measured on `select 1;\nselect 2;\nselect 3;` with lines 1–2 selected
(`setSelection(0, 0, 1, len("select 2;"))`), driving the real `SqlEditor`:

```text
before      : 'select 1;\nselect 2;\nselect 3;'
after 1st   : '-- select 1;\n-- select 2;\nselect 3;'
selection   : (0, 0, 2, 0)   lineLength(1) = 13     <- normalised onto line 2
after 2nd   : 'select 1;\nselect 2;\n-- select 3;'
ROUND TRIP OK: False
```

The second toggle operates on lines 1–3: it uncomments the two lines the user
selected **and comments line 3, which was never selected**. In the editor this is
`Ctrl+/` twice leaving the document dirtier than it started, with damage creeping
one line further down on every repetition.

This is precisely the plan requirement that must hold: *"if there was a
selection, the same line range is still selected afterwards, so pressing `Ctrl+/`
twice round-trips"*.

## Why your test did not catch it

`test_sql_editor_toggle_comment_preserves_selected_line_range_for_round_trip`
selects through line 1 of a **two**-line document. Line 1 is the last line and
carries no trailing newline, so `lineLength(1)` happens to equal the visible text
length and the bug is invisible. The assertion
`getSelection() == (0, 0, 1, len("-- select 2;"))` passes for the wrong reason.

Any selection that ends before the end of the document exposes it.

## Required changes

### MECHANICAL — clamp the restored end column to the line's text

In `SqlEditor.toggle_comment`, replace:

```python
                self.setSelection(line_start - 1, 0, line_end - 1, self.lineLength(line_end - 1))
```

with:

```python
                end_line = line_end - 1
                end_column = len(self.text(end_line).rstrip("\r\n"))
                self.setSelection(line_start - 1, 0, end_line, end_column)
```

This patch was applied and measured by the reviewer before being prescribed.
Both cases pass with it in place:

```text
mid-document: sel_after_1st=(0, 0, 1, 12) round_trip_ok=True
final line  : sel_after_1st=(0, 0, 1, 12) round_trip_ok=True
```

The reviewer's working tree was reverted afterwards; the patch is yours to apply.

### MECHANICAL — add the regression test

Extend `tests/test_sql_editor.py` with a round-trip test whose selection ends on a
**non-final** line. Minimum shape:

- document `select 1;\nselect 2;\nselect 3;`;
- `setSelection(0, 0, 1, len("select 2;"))`;
- one `toggle_comment()` — assert the text is
  `-- select 1;\n-- select 2;\nselect 3;` and that `getSelection()` ends on line
  `1`, not line `2`;
- a second `toggle_comment()` — assert the document is byte-identical to the
  original, **including that line 3 is still uncommented**.

Record the red output of this test against the current implementation before
fixing it. It must fail on the pre-fix code; if it passes, it is not exercising
the defect.

Keep the two tests you already added — they are correct as far as they go.

## Gate status

Re-run by the reviewer:

```text
tree: clean before review
```

The full suite was not re-run this round; the defect above is reproducible
directly against `SqlEditor` and blocks acceptance regardless of the tally.

## Not at issue

- The undo behaviour is correct: `beginUndoAction` / `endUndoAction` wrap the
  edit, and one `undo()` restores the original text.
- `test_sql_editor_toggle_comment_round_trips_selection` was correctly left
  unmodified.
- Capturing `has_selection` and the cursor position **before** mutating the
  document is the right order.
- Inlining the replace rather than delegating to `set_text_undoable` is
  accepted — the selection restore has to live inside the same undo action.

STATUS: CHANGES_REQUESTED
