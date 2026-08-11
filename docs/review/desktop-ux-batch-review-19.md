# Review — desktop-ux-batch (round 19, final)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commits reviewed: `387efba feat(schema): select individual schema cells`,
`303b8a0` and `2f8fc4a` (session-log records of the Verification section)

## Verdict

**Task 15 accepted. All fifteen tasks are complete.** No further implementation
rounds. Do not run `finalize`; integration into `dev` is the orchestrator's job
and is being performed now.

## Gate status

Run by the reviewer, independently of the session log:

```text
git status --porcelain : (empty)
ruff check .           : All checks passed!
ty check src/          : All checks passed!
pytest                 : 544 passed, 7 deselected in 14.29s
untracked files        : (none)
```

### Independent verification of Task 15

1. **Mutation — restore the unconditional `selectRow(index.row())`:**

   ```text
   FAILED tests/test_schema_panel.py::test_schema_panel_cell_selection_keeps_column_names_and_context_selection
   1 failed, 13 passed
   ```

   The context-menu fix is genuinely covered; a right-click no longer collapses a
   multi-cell selection. Reverted.

2. **The `copy_selection` report was verified, not taken on trust.** Your session
   log states that a scattered selection copies whole rows rather than the picked
   cells. Reproduced directly against `SchemaPanel` with `(0, 0)` and `(1, 1)`
   selected:

   ```text
   selected cells: [(0, 0), (1, 1)]
   clipboard rows: 2
      'id\tBIGINT\tUnknown\t1\t\t\t\t\t'
      'name\tVARCHAR\tUnknown\t2\t\t\t\t\t'
   ```

   Accurate in both directions: rows are **not** misaligned, and exact scattered
   cells are **not** preserved. Reporting rather than rewriting the serializer was
   the correct call, and the finding is recorded in `out_of_scope_findings`.

## On V9 — the in-repo `__pycache__` is pre-existing, not yours

Your V9 run found `./src/wherewolf/__pycache__` and deleted it. It reappears on
every full-suite run, so deleting it is not a fix. The reviewer established
provenance rather than leaving it ambiguous:

```text
full suite on feat/desktop-ux-batch : 544 passed -> src/wherewolf/__pycache__ REAPPEARS
full suite on dev (499 passed)      -> src/wherewolf/__pycache__ REAPPEARS, same four files
                                        (_build_info, cli, __init__, __main__)
```

`run.sh` exports `PYTHONPYCACHEPREFIX=/tmp/wherewolf/__pycache__`, but those four
modules are the CLI entry path — consistent with a test spawning a fresh
interpreter that does not inherit the variable. **This predates the branch** and
is a standing `CLAUDE.md` §5 gap, not a defect in this work. Add it to
`out_of_scope_findings` for a separate plan; do not attempt a fix here.

## Verification section

Your V1–V7 records match the reviewer's own per-round mutations, which were run
independently at each round and are the authority for this branch. Two of those
rounds found defects your V-section could not have caught, because they were
defects in the tests rather than the code (rounds 11 and 16).

## Plan coverage

All five areas are complete:

- **Area 1** — `Ctrl+/` reaches Toggle Comment (Task 1).
- **Area 2** — every `setText` path is undoable: history restore and apply-order
  (Task 2), toggle comment (Task 3), replace all (Task 4).
- **Area 3** — severity colours (Task 5) and the Messages tab raised only on
  execution failure (Task 6).
- **Area 4** — persisted auto-size settings (Task 7), clamped resize with a
  bounded precision (Task 8), Preferences UI (Task 9).
- **Area 5** — history delete-by-id (Task 10), SQL serialisation (Task 11),
  multi-select and confirmed delete (Task 12), save-as-SQL (Task 13), catalog
  cell selection (Task 14), schema cell selection (Task 15).

Out-of-scope items were held out as the plan required: no catalog `Ctrl+C`, no
`QUndoStack`, no changes to the dead undo/redo/cut/copy/paste shortcuts, and
Clear History still does not confirm.

## Next

Nothing. Stop polling and exit cleanly.

STATUS: CHANGES_REQUESTED
