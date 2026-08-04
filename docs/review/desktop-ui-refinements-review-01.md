# Review — desktop-ui-refinements (round 01)

Branch: `feat/desktop-ui-refinements`
Reviewed against: `docs/plans/2026-08-03_desktop-ui-refinements.md`
Reviewed at: `df1f5dd7824c0bc4b497de28e385290d384ae675`

## Verdict

All nine tasks are implemented and land as separate conventional commits in plan
order. I verified every one against the running application under an offscreen
Fusion dark palette, not just against the test suite — 11 live checks, 0 failures.
One finding blocks: a test whose assertion was inverted while its name was left
in place, taking real coverage with it.

## Gate status

Independently re-run by the reviewer:

- `./run.sh uv run pytest` → **461 passed, 7 deselected**, exit 0.
- `./run.sh uv run ty check src/` → `All checks passed!`, exit 0.
- `./run.sh uv run ty check .` → `All checks passed!`, exit 0.
- `scripts/check_cache_budget.sh` → exit 0, `cache bytes: 2501605569` (58% of the
  4 GiB ceiling).

## Live application verification

Driven offscreen against the real `MainWindow`:

| Check | Result |
|---|---|
| `Ctrl+Q` present on the Quit action | PASS — `['Ctrl+Q', 'Exit']`, exact match |
| Preview-rows input constrained | PASS — `maximumWidth=57px` |
| Alternating row colors | PASS — base `#232323` vs alt `#2d2d2d` |
| Columns movable in all four views | PASS — results/catalog/schema/history all True |
| A catalog column actually moves | PASS — `visualIndex(0)` 0 → 1 |
| Editor h-scrollbar follows content | PASS — hidden on `SELECT 1`, shown on a 200-column line |
| Five themes, distinct papers | PASS — `#1e1e1e / #ffffff / #002b36 / #fdf6e3 / #000000` |
| Help → SQL Dialect Reference submenu | PASS — all 7 dialects present |
| Dialect link opens the right URL | PASS — DuckDB → `https://duckdb.org/docs/stable/sql/introduction` |
| Export button opens a modal | PASS — `ExportOptionsDialog`, `isModal()` True |

The export modal renders with both controls labelled and OK/Cancel, and the
inline format/scope combos are gone from the results row. Task 4's
`test_manual_profile_bypasses_over_limit_auto_profile_gate_and_updates_schema_panel`
is exactly the test the plan asked for: it sets `profile_max_bytes` to 0, asserts
the auto-profile was skipped with a recorded reason and no worker queued, then
asserts the Profile button queues one anyway.

## Required changes

### Finding 1 (blocking) — an inverted assertion under an unchanged test name, and lost coverage

Task 1's carried-over cleanup ("a warning is pushed to the status bar twice —
make it once") was implemented by deleting the `error_reported` emission from
`CatalogDock.add_paths` (`catalog_dock.py:90`). The de-duplication itself is
correct: warnings now reach the user once, through `_handle_add_result` →
`_show_status`.

The problem is what happened to the test. In `tests/test_catalog_dock.py`:

```python
-    messages: list[str] = []
-    window.catalog.error_reported.connect(messages.append)
+    warning_spy = QSignalSpy(window.catalog.error_reported)
...
-    assert len(messages) == 1
-    assert "Unsupported source format" in messages[0]
+    assert len(warning_spy) == 0
```

The function is still named
`test_catalog_dock_drag_drop_unsupported_files_are_single_warning_and_still_adds_supported`.
It now asserts **zero** warnings. A future reader trusting the name will believe
the single-warning path is covered when the test asserts its opposite.

More consequentially, the assertion on message *content* was deleted and not
relocated. Nothing now verifies that dropping an unsupported file surfaces a
warning to the user at all:

- `tests/test_catalog_service.py:95` proves the service *produces* the warning;
- no test proves it *reaches* the status bar.

The delivery path (`_handle_add_result`'s `if result.warnings:` branch) is
therefore untested, which is precisely the code the cleanup touched.

Required:

- rename the test to describe what it now asserts — that the dock no longer
  emits `error_reported` for add-time warnings, because MainWindow owns that
  surface;
- add a MainWindow-level test that drops an unsupported file and asserts the
  status bar contains `Unsupported source format`. That restores the lost
  coverage at the layer that now owns the behavior;
- confirm by mutation: delete the `if result.warnings:` branch in
  `_handle_add_result` and record that the new test goes red. If it stays green,
  the test is not testing delivery.

## Non-blocking observations

1. The alternating-row contrast is genuinely subtle at `#232323` vs `#2d2d2d` —
   about 10 levels of luminance. That came from the palette *I* supplied in the
   capture harness, not from your code, and the plan's rule (only override
   `AlternateBase` when it equals `Base`) was followed correctly. Flagging only so
   it is on the record that striping visibility depends on the host palette.
2. `SQL_DIALECT_REFERENCE_URLS` pins versioned documentation URLs for Oracle
   (`/23/`) and MySQL (`8.4`). Those will rot. Not worth changing now; worth a
   comment noting they need periodic review.

## Confirmed sound

- no review notes deleted; working tree clean apart from the user's pre-existing
  untracked `feature-ideation-workbench-depth.md`;
- the ty `unresolved-import` suppression is still narrowly scoped — V4 probe
  re-run: a bogus import in `src/` still fails ty with the correct diagnostic, so
  nobody re-broadened it;
- test count moved 447 → 461;
- `tests/test_ui_legibility_toolbar.py` dropping `export_format_selector` from its
  labelled-controls map is correct and expected, since that control moved into the
  modal — and the modal labels both of its controls.

STATUS: CHANGES_REQUESTED
