# Review — desktop-ux-batch (round 08)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `29eab17 feat(settings): persist result column auto-size preferences`

## Verdict

**Task 7 accepted — proceed to Task 8.**

Both settings follow the `preview_limit` quartet exactly: private key helper,
public key property, validating restore, clamping save. Constants sit with the
other `DEFAULT_*` entries. Defaults are `True` / `300` as the user decided.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      510 passed, 7 deselected in 13.39s   (509 before this task — one new test)
git status:  clean (empty --porcelain)
```

### Independent verification performed

1. **Persistence survives an app restart.** The tests exercise one
   `SettingsService` instance, which can mask an INI round-trip bug because
   QSettings caches values in memory. Saved `False`/`450` through one instance,
   synced, then read through a **fresh** `QSettings` on the same file:

   ```text
   same instance : False 450
   fresh instance: False 450
   raw types     : bool int
   ini contents  : [v1] | results\auto_size_columns=false | results\auto_size_max_width=450
   ```

   PyQt6 converts the INI strings back to `bool`/`int`, so turning auto-size off
   and restarting the app keeps it off. This is the failure mode that would have
   made the feature flag feel broken to the user; it does not occur.

2. **Mutations.**

   ```text
   A: drop the save-side clamp             -> FAILED
   B: drop the restore-side range check    -> FAILED
   C: drop the isinstance(value, bool) guard -> PASSED
   ```

   A and B confirm both halves of the validation are covered. All reverted.

## Required changes

None for Task 7.

## Non-blocking observation

Mutation C shows the `isinstance(value, bool)` guard in
`restore_auto_size_max_width` is not independently reachable by any test: `True`
already fails `50 <= value <= 2000` because `True == 1`. The guard is therefore
redundant here rather than wrong. **Keep it** — it matches the neighbouring
`restore_preview_limit` and `restore_editor_font_size` idiom, and consistency in
this file is worth more than removing a dead branch. Recorded so the coverage
gap is not mistaken for a tested behaviour.

## Next

Begin **Task 8 — Clamped auto-size in the results view**. Three things the plan
is specific about: default the stored policy to `True`/`300` so a view built
without the setter still behaves like the shipped default; call the resize from
`set_frame` only when the flag is on; and set
`setResizeContentsPrecision(200)` on the horizontal header in `__init__` so a
100 000-row preview cannot stall the resize. The second test case — flag off, wide
column **not** clamped — is what stops a hardcoded clamp from passing.

STATUS: CHANGES_REQUESTED
