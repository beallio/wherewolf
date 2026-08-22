# Review — results-grid-selection-fixes (round 01)

Branch: `feat/results-grid-selection-fixes`
Reviewed against: `docs/plans/2026-08-22_results-grid-selection-fixes.md`
Reviewed at: `9a918c6`

## Verdict

The three plan items are implemented and the defect fix is correct and minimal — the
`isColumnHidden` filter was dropped from the `column_order` comprehension only, both consumers
were left untouched, and the docstring now states the map is addressable by visual position.
Every test the plan named exists. Gates were re-run independently by the reviewer and pass.

Blocked on one defect introduced by this round: `selection_statistics()` raises on a selection
that spans a numeric column and a nested column, which is reachable from ordinary JSON data.

## Gate status

Re-measured by the reviewer at `9a918c6`, not taken from the session log:

- `ruff check .` — All checks passed!
- `ruff format --check .` — 182 files already formatted
- `ty check src/` — All checks passed!
- `pytest` — `662 passed, 7 deselected in 20.33s` (baseline 648, so 14 tests were added)
- `git diff --stat dev...HEAD -- pyproject.toml uv.lock` — empty, as required
- `git status --short` — clean

## Required changes

### 1. BLOCKING — `selection_statistics()` raises on numeric + nested selections

`ResultTableView.selection_statistics()` concatenates per-column gathers with
`pl.concat(..., how="vertical_relaxed")` before it decides whether the selection is numeric.
`vertical_relaxed` needs a common supertype, and there is none for a numeric column and a
`List` column, so the call raises instead of returning statistics.

Measured through the real signal path — `sm.select(...)` on a frame of
`{"n": [1, 2], "l": [[1, 2], [3]]}`, selecting `(0,0)` then `(0,1)`:

```text
polars.exceptions.SchemaError: failed to determine supertype of i64 and list[i64]
```

The exception surfaces inside `_emit_selection_statistics`, which is connected to
`selectionChanged`. Under `pytest-qt` that becomes a test failure; in the packaged application an
unhandled exception in a Qt slot follows PyQt6's default policy, and nothing in `src/` installs an
excepthook to soften it. At best the selection summary silently stops updating; at worst the
process aborts.

This is not an exotic input. `read_json_auto` produces `List` columns for JSON arrays, and JSON is
one of the advertised source formats, so any user selecting across a JSON array column and a
number hits it.

A second, quieter symptom of the same design: for `{"n": [1, 2], "j": [{"k": 1}, {"k": 2}]}` with
cells `(0,0)` and `(0,1)` selected, the result is
`SelectionStatistics(cell_count=2, distinct_count=1, null_count=0, numeric=None)` — two visibly
different values reported as one distinct value, because the relaxed concat coerced them together.
The displayed number is wrong.

**Fix direction:** do not concatenate values across columns of different dtypes. Decide
`selected_columns_are_numeric` first; take the numeric aggregate path only in that case. For the
counts, aggregate per column and combine the results — or cast each gathered column to `String`
before concatenating, so distinct and null counts are computed on a common, lossless
representation. Either way the mixed-dtype path must never depend on a supertype existing.

**Tests to add** (both must be observed failing first):

- a selection spanning a numeric column and a `List` column returns statistics with
  `numeric is None` rather than raising;
- a selection spanning a numeric column and a `Struct` column reports `distinct_count == 2` for
  two different values.

### 2. Verification artifacts required by the plan are missing from the session log

`docs/agent_conversations/2026-08-22_results-grid-selection-fixes.json` records the baseline, the
three RED observations, the targeted tallies and the gates. Good, and the RED evidence is
genuinely strong. Two required items are absent:

- **Verification §2, mutations 2a/2b/2c.** The plan asks for three named mutations applied *after*
  implementation — re-add the `isColumnHidden` filter; stub `selection_statistics()` to return
  `None`; render the inspector with `str(value)` — each with the resulting tally and a restore.
  RED-before-implementation is related evidence but it is not the same check: it does not show that
  the tests still bite against the finished code. Record the three tallies.
- **The "Deferred and unverified" statement.** The plan requires it to be stated explicitly in the
  round-complete report rather than implied; the log contains no such section (no occurrence of
  "defer"). State the four items the plan lists: no manual GUI verification, no performance
  measurement behind the single-pass aggregation or the inspector size cap, no Spark coverage, and
  no audit for other callers resolving columns by visual index.

## Not required, recorded for the audit trail

- `Ctrl+I` is scoped `WidgetWithChildrenShortcut` on the results view, so it does not collide with
  the editor's shortcuts. Given release 0.9.2 dealt with exactly that class of collision, the
  scoping is the right call.
- Setting the clicked index current in `_on_body_context_menu_requested` before opening the menu
  resolves the trap the plan called out; `inspect_current_cell` reads `UserRole` rather than going
  through `format_cell_value`, as required.
- The inspector reuses the `ValueCountsWindow` lifetime pattern including the shutdown sweep.

STATUS: CHANGES_REQUESTED
