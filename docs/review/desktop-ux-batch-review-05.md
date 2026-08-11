# Review — desktop-ux-batch (round 05)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `f25810c fix(editor): make replace all undoable`

## Verdict

**Task 4 accepted — proceed to Task 5.**

`replace_all` now routes through `set_text_undoable`. The return value
(`current.count(old_text)`) and the `current == replaced` early return are both
preserved, as required.

The test is well constructed: it makes a normal edit (`insert("!")`) *before*
calling `replace_all`, then asserts that one `undo()` yields
`"alpha beta alpha!"` — the replace is undone while the earlier edit survives.
That is the assertion that proves the undo buffer was not wiped, rather than
merely that an undo entry exists.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      506 passed, 7 deselected in 14.24s   (505 before this task — one new test)
git status:  clean (empty --porcelain)
```

### Independent verification performed

**Mutation — the test is not vacuous.** Reverted `replace_all` to
`self.setText(replaced)` and re-ran the focused tests:

```text
FAILED tests/test_sql_editor.py::test_sql_editor_replace_all_is_undoable
1 failed, 1 passed, 27 deselected
MUTATION exit: 1
```

The pre-existing `test_sql_editor_find_and_replace_all` still passes under the
mutation, correctly localising the failure to the new behaviour. Reverted.

## Required changes

None for Task 4.

## Area 2 of the plan is now complete

All three `setText` paths identified in `## Context` are undoable: history
restore and apply-order (Task 2), toggle comment (Task 3), replace all (Task 4).
The `setText` override itself remains, correctly, for genuine document loads.

## Next

Begin **Task 5 — Colour message severities**. Two things the plan is specific
about: resolve light vs dark from the **widget's own palette** (the idiom at
`ResultTableView.__init__`), not from a new settings dependency; and the test
must assert the error colour **differs** from the info colour, since asserting
only that a foreground was set would pass against a black default.

STATUS: CHANGES_REQUESTED
