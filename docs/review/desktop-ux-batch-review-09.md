# Review — desktop-ux-batch (round 09)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `e10d57e feat(results): auto-size result columns with a width cap`

## Verdict

**Task 8 accepted — proceed to Task 9.**

`set_auto_size_policy` stores the flag and cap, the defaults on the class are
`True`/`300` so a view built without the setter behaves like the shipped default,
`set_frame` resizes only when the flag is on, `auto_size_columns` clamps every
visible column, and `setResizeContentsPrecision(200)` is set on the horizontal
header in `__init__`.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      511 passed, 7 deselected   (510 before this task — one new test)
git status:  clean (empty --porcelain)
```

### Independent verification performed

1. **Mutations.**

   ```text
   A: remove the width clamp            -> FAILED
   B: ignore the enabled flag entirely  -> FAILED
   ```

   B is the one that matters: it proves the "flag off ⇒ not clamped" case is
   load-bearing rather than decorative. Both reverted.

2. **The benchmark the plan deferred — now measured.** 12 string columns,
   `set_frame` timed with the policy off and on:

   ```text
     1,000 rows x 12 cols | auto-size OFF  0.032s | ON  0.108s | added  0.076s
    10,000 rows x 12 cols | auto-size OFF  0.373s | ON  0.452s | added  0.079s
   100,000 rows x 12 cols | auto-size OFF  4.858s | ON  4.892s | added  0.034s
   ```

   **Auto-size costs a flat ~30–80 ms regardless of row count** — exactly what
   `setResizeContentsPrecision(200)` is supposed to buy, and it is buying it. At
   the shipped `DEFAULT_PREVIEW_LIMIT` of 1000 rows the user pays 76 ms.

   For contrast, with the precision bound removed (`-1`, scan every row) the same
   100 000-row frame takes **43.3s** versus 4.9s — an 8.7x penalty. Do not remove
   that line in a later task.

3. **Clamp holds at scale**: all 12 columns of the 100 000-row frame came back
   `<= 300`.

## Out-of-scope finding — record it, do not fix it here

The 4.86s in the `auto-size OFF` column at 100 000 rows is **pre-existing**
`set_frame` cost (model reset plus proxy), unrelated to this task and present
before this branch. It is reachable today by raising the preview limit toward
`MAX_PREVIEW_LIMIT`. Note it in the session log for a separate plan; do not
touch it here.

## Non-blocking observations

- `assert disabled_table_view.columnWidth(0) != 120` would read better as `> 120`.
  Mutation B shows the current form is still load-bearing, so this is style only.
- `set_auto_size_policy` does not re-apply to a frame that is already displayed;
  the new cap takes effect on the next `set_frame`. That is acceptable and the
  plan did not require otherwise, but keep it in mind for Task 9 — changing the
  width in Preferences will not visibly resize the current result until the next
  query. If you want it to, call `auto_size_columns()` from the setter when a
  frame is present, and say so in the session log.

## Next

Begin **Task 9 — Expose auto-size in Preferences**. The assertion that catches a
missing `_restore_state` wiring is the last one: construct a **fresh**
`MainWindow` against the same `QSettings` and confirm the restored view carries
the saved width. Round 08 verified the settings themselves survive a restart, so
any failure there is wiring, not persistence.

STATUS: CHANGES_REQUESTED
