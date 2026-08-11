# Review — desktop-ux-batch (round 17)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `b7cc22e fix(history): share SQL destination normalisation`

## Verdict

**Task 13 accepted — proceed to Task 14.**

`normalise_sql_destination` is now the single source of the rule, both services
call it, and the production wrapper is tested directly. The fake can no longer
drift from production because it no longer has its own copy.

**Area 5's history half is complete**: multi-select, right-click delete behind a
confirmation, and save-selected-as-SQL.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      541 passed, 7 deselected in 14.06s   (532 before Task 13 — nine new tests)
git status:  clean (empty --porcelain)
```

### Independent verification performed

The round-16 mutation, repeated:

```text
strip the suffix call from QtFileDialogService -> 1 failed, 540 passed   (was: 534 passed)
```

It now fails on the suffix-less parameter case. The gap is closed.

A second mutation, aimed at the extracted helper itself:

```text
make the helper rewrite every suffix (drop the `if destination.suffix` guard)
  -> 2 failed: the direct helper test AND the QtFileDialogService test,
     both on the /tmp/history.txt case
```

That is the case worth having: a user who deliberately types `queries.txt` keeps
`.txt`. Both layers catch it. All mutations reverted.

## Required changes

None for Task 13.

## Next

Begin **Task 14 — Cell selection in the dataset catalog**. This is the task the
plan singles out as the highest-risk change on the branch, because switching
`CatalogDock` to `SelectItems` silently breaks every context-menu action unless
`_selected_entry` is fixed **in the same commit**. `selectedRows()` returns an
empty list once rows are no longer selected whole, which turns rename, remove,
refresh, copy alias, copy path, insert alias, and reveal into no-ops.

The plan requires three assertions. The second — that `Remove` and `Copy Alias`
still act on the right entry with only a **single cell** selected — is the
regression guard, and final verification will mutate `_selected_entry` back to
`selectedRows()` to confirm it bites.

For the third, use `QTest.mouseClick` on `verticalHeader().viewport()`. Do not use
`sectionClicked.emit`: it changes no selection and produces a vacuous test.
Round 15 also showed that Qt's own `mousePressEvent` drives some selection
behaviour, so prefer assertions about which entry an **action operates on** over
assertions about selection state where you can.

Leave `ElideMiddle` and the `Stretch` mode on the File column untouched.

STATUS: CHANGES_REQUESTED
