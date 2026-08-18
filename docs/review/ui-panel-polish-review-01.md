# Review 01 — ui-panel-polish

**Branch:** `feat/ui-panel-polish`
**Head reviewed:** `541f01c`
**Base:** `dev` (`1685b16`)
**Gates as re-run by the reviewer:** `563 passed, 7 deselected`, coverage 90%. Baseline on
`dev` was `555 passed`, so this round adds 8 tests. `run-quality-gates` passes, tree clean,
no review notes deleted.

## Summary

Good round. All eight tasks landed as eight separate commits with correct atomicity, and
all eight planned mutations were re-run independently by the reviewer and every one turns
its suite red. One real defect blocks the round, plus one test gap and one nit.

Reviewer-verified mutation results (re-measured, not read from the session log):

| Mutation | Result |
|---|---|
| 1 — `_set_result_summary` no-op | `1 failed, 99 passed` |
| 2 — drop the `truncated` clause | `1 failed, 99 passed` |
| 3 — identity uses `path` not `path.name` | `1 failed, 15 passed` |
| 4 — skip re-applying the column filter | `1 failed, 15 passed` |
| 5 — numeric `EditRole` data removed | `1 failed, 12 passed` |
| 6 — `QSplitter` replaced by layout adds | `1 failed, 12 passed` |
| 7 — `_last_result` not cleared on error | `2 failed, 11 passed` |
| 8 — export format hardcoded to CSV | `1 failed, 12 passed` |

Task atomicity was respected throughout, including the C3/C4 split (`19404d8` retains the
result, `3428edc` adds the export) that the plan called out specifically.

---

## MECHANICAL — must fix

### M1. The schema panel tooltip goes stale and points at the wrong file

`src/wherewolf/desktop/widgets/schema_panel.py:295`

`setToolTip` is called only inside the `alias is not None` success branch. Every other
branch — schema error, no columns, inspection pending, no table selected — leaves the
tooltip untouched, so it keeps whatever path was set for the *previously* displayed
dataset.

Reviewer-reproduced:

```text
after good entry -> tooltip=/data/exports/2026/customers.parquet
status  -> loans — Schema error: could not read file
tooltip -> /data/exports/2026/customers.parquet     <-- stale, wrong file
```

Select a dataset that fails to read and the panel says `loans` while hovering it reports
`customers.parquet`. This is the exact defect class this plan exists to fix — the panel
misidentifying which file the user is looking at — and it is worse than the original bug
because a confidently wrong path is more misleading than a truncated one.

**Fix:** clear the tooltip alongside the warning label, which `_update_view` already does
unconditionally at `:264-265`. Add a third line there:

```python
        self._warning_label.clear()
        self._warning_label.hide()
        self._status_label.setToolTip("")
```

The existing `setToolTip(str(self._entry.path))` at `:295` then re-populates it for the
success branch only, which is correct.

**Test:** assert that after displaying a good entry and then an entry with a
`schema_error`, `panel._status_label.toolTip()` is either empty or the *new* entry's path
— never the previous entry's. That test fails against the current code.

---

## MECHANICAL — minor

### M2. Splitter orientation is not asserted

`tests/test_value_counts_window.py:99-106`

The splitter test checks `count()`, both child widgets, and that `setSizes` takes effect,
but never the orientation. A `QSplitter(Qt.Orientation.Horizontal, ...)` passes every one
of those assertions while putting the table and chart side by side instead of stacked —
a clearly wrong layout that no test would catch. Reviewer-verified: flipping the
orientation to `Horizontal` leaves `tests/test_value_counts_window.py` fully green at
`13 passed`.

Add:

```python
    assert window.content_splitter.orientation() == Qt.Orientation.Vertical
```

---

## DESIGN — author's call

### D1. Truncation is now reported twice

`main_window.py:918-928` already renders `result_truncation_notice` ("Preview is truncated
at the selected row limit. Export Full Results for all rows."), and the new summary strip
adds `· truncated at N preview rows` immediately above it. Both are correct and the
redundancy is harmless, but two adjacent labels saying the same thing is noise. Consider
folding the standing notice into the summary strip, or leaving it — your call, and not
worth a round on its own.

---

## Confirmed good

- The identity line uses `path.name` and no longer leaks the parent directory; warnings
  moved cleanly onto a separate `_warning_label` so a long warning cannot push the dataset
  name around.
- Coverage for the profiling-warning clauses was **preserved, not weakened** — the
  assertions in `tests/test_main_window.py:2067,2108` were repointed from `status_text()`
  to `warning_text()` and still assert the same strings. This was the change the plan
  authorised, and it was done correctly.
- `_apply_column_filter` is called at method level in `_update_view`, so it re-applies on
  every repopulation and in every branch, not just the success path.
- The numeric sort fixture uses 9 / 100 / 25 — genuine lexical-vs-numeric disagreement,
  not single digits. `_NumericTableWidgetItem` stores the number under `EditRole` (which
  `QTableWidgetItem` normalises to `DisplayRole`, giving numeric `operator<`) while
  overriding `text()` so the existing TSV clipboard test still sees `75.00%`. The
  `setSortingEnabled(False)` / `True` bracket around repopulation is present.
- `choose_value_counts_path` was added to **all three** of the `Protocol`, `FakeFileDialogService`,
  and `QtFileDialogService`, and the ad-hoc fake in `tests/test_actions.py:75-83` was
  updated too. Omitting any of these would have broken every injecting test.
- Export format is selectable and defaults from `restore_export_format()` rather than
  being hardcoded, and the chosen format is saved back.
- `_set_result_summary("")` is called on `RUNNING`, so a stale summary never sits over
  fresh results.

---

## Required before the next round

1. Fix M1 and add the tooltip-staleness test.
2. Add the orientation assertion from M2.
3. Re-run `scripts/orchestration/run-quality-gates` and record the tallies.

STATUS: CHANGES_REQUESTED
