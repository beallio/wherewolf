# Review — desktop-ux-batch (round 06)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `6fd05a7 feat(messages): colour message severities`

## Verdict

**Task 5 accepted — proceed to Task 6.**

`message_severity_color(severity, palette)` lives in `theming.py`, is exported
through `__all__`, and resolves light vs dark from the supplied palette's `Base`
lightness — the idiom the plan asked for, with no new settings dependency.
`MessagesPanel._append_item` applies it via `setForeground`, and the existing
`UserRole` severity data and `message_at` contract are untouched.

The WCAG contrast test in `tests/test_theming.py` goes beyond what the plan
required and is the right instinct. Note for your own calibration: a hand-rolled
contrast helper is itself untested code, so the reviewer recomputed the ratios
independently rather than trusting it.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      508 passed, 7 deselected in 13.43s   (506 before this task — two new tests)
git status:  clean (empty --porcelain)
```

### Independent verification performed

1. **Contrast recomputed without your helper**, against the real palettes:

   ```text
   Light error   #b3261e on #ffffff contrast=6.54
   Light warning #7a4e00 on #ffffff contrast=7.20
   Light info    #005ac1 on #ffffff contrast=6.50
   Dark  error   #ffb4ab on #1e1e1e contrast=9.82
   Dark  warning #ffb95d on #1e1e1e contrast=9.80
   Dark  info    #a8c7fa on #1e1e1e contrast=9.70
   ```

   All six clear 4.5:1 with margin, so the `>= 4.5` assertion is satisfied by the
   colours rather than by a defect in the helper. Both error shades are
   unambiguously red-dominant.

2. **Mutation — the tests are not vacuous.** Collapsed
   `message_severity_color` to always return the error colour:

   ```text
   FAILED tests/test_theming.py::test_message_severity_colours_are_distinct_and_readable_in_both_themes
   FAILED tests/test_messages_panel.py::test_messages_panel_colours_error_and_info_by_severity
   2 failed, 7 passed
   MUTATION exit: 1
   ```

   Both layers catch it — the theming-level distinctness check and the
   panel-level "error differs from info" check. Reverted.

## Required changes

None for Task 5.

## Non-blocking observations

- Items already in the list keep their colour if the user switches theme
  mid-session; only newly appended messages pick up the new palette. This was
  called out as acceptable when the plan was written. Do not fix it here.
- `test_messages_panel_colours_error_and_info_by_severity` pins the literal
  `#b3261e`. That is fine, but it means any future palette change must update
  this test — record that in the session log rather than silently editing the
  expectation later.
- The panel test reaches into `panel._list_widget`, a private attribute. The
  existing tests in that file use the public `message_at` accessor. Not worth a
  round, but prefer the public accessor if you touch this test again.

## Next

Begin **Task 6 — Raise the Messages tab on execution failure**. The plan requires
**three** assertions, and the second and third are what stop the feature from
being a tab-switch that fires unconditionally: a `SUCCEEDED` result must not
change the current tab, and editor diagnostics must not change it either.

STATUS: CHANGES_REQUESTED
