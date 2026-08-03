# Review — ui-refinements (round 02)

Branch: `feat/ui-refinements` @ `d13b8db`
Reviewed against: `docs/plans/2026-08-02_ui-refinements.md` and review 01

Tasks 1–4 by `gpt-5.6-terra`, tasks 5–7 by `gpt-5.6-luna` after a mid-round model switch.

## Verdict

APPROVED.

## Gate status

```text
ruff check   All checks passed
ty check .   All checks passed
pytest       428 passed, 7 deselected
git status   clean
```

## K1 — fixed, and the guard now bites

The dtype-icon assertion compares **rendered content** rather than object identity.
Re-running the mutation that round 01 sailed through:

```text
_dtype_family() -> "text"     distinct by content: 1 of 4
full suite                    1 failed, 427 passed
FAILED tests/test_result_table_view.py::
       test_result_table_view_headers_show_distinct_dtype_icons_and_tooltips
       assert 1 == 4
```

Round 01 reported `428 passed` under the identical mutation. The guard is real now.

The lesson is worth keeping: `QIcon.cacheKey()` is per instance and reports distinct values
for icons drawn identically. Any assertion about two icons being *different* has to compare
pixels — render to a pixmap, serialise, and compare digests. My own first verification made
this mistake and would have approved an unfailable test.

## Carried forward from review 01 — still verified

R1 theme in Preferences, off the toolbar. R2 chronological history sorting. R3 per-dock
View-menu toggles restoring without disturbing siblings. R4 alternating rows on history,
catalog and schema. R5 four distinct dtype icons with dtype tooltips. R6 Export button in
the results section, visible at 1024px, Query-menu actions retained. R7 SQL predicates,
substring fallback, and malformed input preserving rows while showing a real DuckDB
diagnostic.

## Negative controls — full suite, baseline 428

| mutation | round 01 | round 02 |
|---|---|---|
| T2 history sorting disabled | 1 failed | — |
| T3 dock toggles removed | 1 failed | — |
| T5 all dtypes one family | **428 passed** | **1 failed** |
| T6 export button hidden | 1 failed | — |
| T7 SQL predicate path forced to fail | 3 failed, 2 errors | — |

## The boundary held

Version `0.5.2`, no tag, `main` untouched. No `QScrollArea` in the toolbar. `timid = true`,
the `pyarrow` import, the overwrite confirmation, `EngineKind` and the `DIALECT_MAPPING`
identifiers all unchanged. The six working features were not altered while fixing the test.

## Deferred

Icon legibility at high DPI, row-banding weight, and toolbar composition after the export
move are manual maintainer checks. Filter expressions evaluate against the **preview** frame
only and cannot reach rows excluded by the preview limit.

Tabbed multiple queries remains unplanned work, to be scoped as `multi-query-tabs`.

STATUS: APPROVED
