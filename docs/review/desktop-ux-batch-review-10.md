# Review — desktop-ux-batch (round 10)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `618ea14 feat(preferences): expose result auto-size settings`

## Verdict

**Task 9 accepted — proceed to Task 10.**

Checkbox and spin box added to `PreferencesDialog` with the `50..2000` range, both
initialised from the settings service; `_apply_preferences` persists both and
pushes them to the view; `_restore_state` applies the stored values at startup.
The spin box is labelled with its unit ("Maximum result column width (px)").

**Area 3 and Area 4 of the plan are now complete** — errors surface in red and
raise the Messages tab, and result columns auto-size behind a persisted,
user-editable cap.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      512 passed, 7 deselected in 13.95s   (511 before this task — one new test)
git status:  clean (empty --porcelain)
```

### Independent verification performed

**Both wiring points mutated separately:**

```text
A: drop the set_auto_size_policy call in _apply_preferences -> FAILED
B: drop the set_auto_size_policy call in _restore_state     -> FAILED
```

Both reverted. B is the assertion the plan specifically asked for — a missing
`_restore_state` wiring is invisible until you construct a second window — and it
is genuinely load-bearing.

## Non-blocking observations

- The restored-window assertions read the private
  `_auto_size_columns_enabled` / `_auto_size_max_width` attributes. A behavioural
  equivalent (set a wide frame on the restored window, assert the width) would
  survive a future refactor of those attribute names. Not worth a round; the
  mutation above shows the current form does catch the bug it is aimed at.
- `assert window.result_table_view.columnWidth(0) < 150` passes because an
  unresized column sits near Qt's ~100 px default, and would fail at exactly 150
  if the policy were wrongly enabled. It discriminates correctly, but the
  reasoning is implicit — a comment would help the next reader.

## Next

Begin **Task 10 — Delete history records by id**. This is the first task in the
history area and it is pure storage: no Qt. Build the survivor list from
`get_all()` so the v1→v2 migration is respected, write through `_write_history`,
return the number removed, ignore unknown ids, and do **not** rewrite the file for
an empty iterable. The plan lists five test cases including the legacy-v1 case —
that one exists because `get_all()` silently migrates, and a delete implemented
against the raw JSON would corrupt it.

STATUS: CHANGES_REQUESTED
