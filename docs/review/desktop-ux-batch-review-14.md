# Review — desktop-ux-batch (round 14)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `192d2d9 fix(history): order SQL export by recorded instant`

## Verdict

**Task 11 accepted — proceed to Task 12.**

The sort now runs on parsed instants, and all three prescribed regression tests
were added. The export is consistent with how the History dock itself orders
records.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      529 passed, 7 deselected in 13.42s   (519 before Task 11 — ten new tests)
git status:  clean (empty --porcelain)
```

### Independent verification performed

```text
mutation: restore the plain ISO-string sort  -> 3 failed, 7 passed
mutation: drop the tzinfo normalisation      -> 1 failed, 9 passed
```

The first proves all three new tests bite on the original defect. The second is
the more interesting one: dropping `parsed.replace(tzinfo=UTC)` fails only the
naive/aware test, which confirms that test is defending the `TypeError` path
specifically rather than passing incidentally alongside the others. Both
reverted.

## Required changes

None for Task 11.

## Non-blocking observations

- The three new tests use `startswith` / `in` rather than asserting the exact
  full document. That is the right choice here — ordering is the property under
  test, and the exact-string assertions in the earlier tests already pin the
  format.
- The `assert isinstance(query, str)` narrowing assert flagged in round 13 is
  still present. Still not worth a round.

## Next

Begin **Task 12 — History multi-select, context menu, and delete**. This is the
first Qt task in the history area. Points the plan is specific about:

- build the `QAction`s once in `__init__` and enable/disable per invocation,
  following `CatalogDock._on_context_menu`;
- right-clicking a row **outside** the current selection reduces the selection to
  that row; right-clicking **inside** a multi-row selection preserves it;
- the confirmation dialog names the record count, and cancelling deletes nothing;
- monkeypatch `QMessageBox` in the `history_dock` namespace — the pattern at
  `tests/test_catalog_dock.py:310` — never let a real modal open.

The delete path goes through `HistoryManager.delete_records`, which rounds 11–12
established is correct and now well covered.

STATUS: CHANGES_REQUESTED
