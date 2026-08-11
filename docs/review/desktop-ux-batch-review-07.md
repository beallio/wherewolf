# Review — desktop-ux-batch (round 07)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `89e92c5 feat(messages): raise the messages tab on execution failure`

## Verdict

**Task 6 accepted — proceed to Task 7.**

The tab widget is now `self.results_tabs`, the switch lives inside the existing
`FAILED` branch, and `_on_editor_diagnostics` was correctly left untouched. All
three plan-mandated assertions are present and all three are load-bearing.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      509 passed, 7 deselected   (508 before this task — one new test)
git status:  clean (empty --porcelain)
```

### Independent verification performed

Three separate mutations, one per assertion, each run against the new test:

```text
A: remove the tab switch entirely            -> FAILED (1 failed, 94 deselected)
B: switch unconditionally, not only on FAILED -> FAILED (1 failed, 94 deselected)
C: let editor diagnostics steal the tab       -> FAILED (1 failed, 94 deselected)
```

All three reverted. Mutation B is the important one: it proves the test would
catch a tab-switch that fires on every result, which was the specific vacuity
risk the plan called out. Mutation C proves the diagnostics carve-out is real.

**On the third assertion:** `window.editor._update_status("editor diagnostic")`
looked at first like it bypassed the diagnostics path. It does not —
`_update_status` emits `diagnostics_reported` with a real `SqlDiagnostic`
(`sql_editor.py:333-345`), which is exactly how the pre-existing
`test_main_window_routes_editor_diagnostic_to_messages_tab` drives the same path.
Following the file's established precedent was the right call.

## On the modified pre-existing assertion

`test_main_window_result_grid_integration` was changed:

```python
-    assert window.result_error_message.isVisible()
+    assert not window.result_error_message.isHidden()
```

This is accepted. The rationale is correct — selecting the Messages tab makes the
Results page non-visible through its ancestor, so `isVisible()` legitimately
becomes `False` for a label that was never hidden — and you recorded it in the
session log under `quality_gate_recovery_task_6`, which is what the plan's scope
discipline requires. Changing a pre-existing expectation is the one place this
plan asks for a paper trail, and you left one.

For the record, a stronger form was available: re-select the Results tab and then
assert `isVisible()`, which would preserve the original assertion's intent
instead of weakening it to "not explicitly hidden". Do not change it now — noted
for calibration only.

## Required changes

None for Task 6.

## Next

Begin **Task 7 — Persist the auto-size preferences**. Follow the
`preview_limit` quartet (`settings_service.py:66`, `130`, `225-239`) because it is
the one that clamps. The plan's test list is specific: out-of-range widths (`5`
and `9999`) must restore as `300`, and a `True` stored in the width key must
restore as `300` rather than `1` — that second case is why the existing code
checks `isinstance(value, bool)` explicitly.

STATUS: CHANGES_REQUESTED
