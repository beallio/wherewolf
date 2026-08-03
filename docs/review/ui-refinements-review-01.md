# Review — ui-refinements (round 01)

Branch: `feat/ui-refinements` @ `776c1e2`
Reviewed against: `docs/plans/2026-08-02_ui-refinements.md`

Tasks 1–4 were implemented by `gpt-5.6-terra`, tasks 5–7 by `gpt-5.6-luna` after a mid-round
model switch. Both halves were reviewed to the same standard.

## Verdict

CHANGES_REQUESTED — **one defect, and it is in a test rather than in the product.** All seven
features work. Task 5's guard does not bite, in exactly the way the plan warned against.

## Gate status

```text
ruff check   All checks passed
ty check .   All checks passed
pytest       428 passed, 7 deselected   (was 420; +8 tests)
git status   clean
```

## Required changes

### K1 — the dtype-icon test cannot fail

The feature itself is correct. Comparing header icons by **rendered pixel content**:

```text
unmutated                     digests: ['e5b60b8c', '4cfda755', '330a4a5b', 'ee119579']
                              distinct by content: 4 of 4
_dtype_family() -> "text"     digests: ['4cfda755', '4cfda755', '4cfda755', '4cfda755']
                              distinct by content: 1 of 4
full suite with that mutation 428 passed, 7 deselected
```

Every result column can render an **identical** icon and the suite stays green. The plan
asked for precisely this assertion:

> Assert that the icons differ from each other — four identical icons would pass a naive
> "icon is not null" check.

**Required change.** Assert that the icons for an integer, a string, a date and a boolean
column differ **by content**, not by object identity. `QIcon.cacheKey()` is per instance and
is useless here — render each icon to a pixmap, save to PNG bytes and compare digests, or
compare `QImage` pixel data directly. Keep the existing not-null and tooltip assertions and
add this one.

**My own first measurement was wrong in the same way and nearly approved this.** I compared
`cacheKey()` values, saw 4 distinct, and recorded a pass. `cacheKey()` differs per `QIcon`
object regardless of what is drawn, so it reports 4 distinct even with the collapse mutation
applied. Only when the mutation appeared to "change nothing" did re-probing by pixel content
reveal both that the mutation *was* effective and that my verification had been meaningless.
Identity is not content.

## Verified and correct — do not revisit

### Tasks 1–4 (terra)

```text
R1  editor_theme_selector no longer on the toolbar; lives in Preferences
R3  View menu: ['Dataset Catalog', 'Schema', 'History', 'Reset Layout', ...]
    close -> toggle -> reopen restores the dock; sibling dock visibility untouched
R4  alternatingRowColors: history=True catalog=True schema=True
```

### Tasks 5–7 (luna)

```text
R5  4/4 non-null icons, 4 distinct by content, tooltips 'age: Int64', 'name: String',
    'when: Date', 'ok: Boolean'                     (feature correct; guard is K1)
R6  'Export' button present and visible at 1024px; format selector visible;
    Query menu still carries Export Preview / Full / Selection
R7  'age > 40'                    -> 3 rows  (45, 61, 52)
    "name = 'bob'"                -> 1 row
    "age >= 45 OR name = 'ann'"   -> 4 rows
    'ann' (plain text)            -> 1 row   substring fallback intact
    'age >'                       -> 5 rows preserved, error shown:
        "Filter error for 'age >': Parser Error: syntax error at end of input"
    'nosuchcol > 1'               -> 5 rows preserved, error names the column and
        suggests candidate bindings
```

R7 is notably good: malformed input preserves the previous rows and reports a real DuckDB
diagnostic in a dedicated `preview_filter_error` label rather than clearing the grid.

## Negative controls — full suite, baseline 428

| mutation | result |
|---|---|
| T2: `setSortingEnabled(False)` on history | 1 failed, 427 passed |
| T3: drop dock `toggleViewAction()`s from the View menu | 1 failed, 427 passed |
| T5: `_dtype_family()` returns one family for everything | **428 passed — K1** |
| T6: hide the results Export button | 1 failed, 427 passed |
| T7: force the SQL predicate path to fail | 3 failed, 425 passed, 2 errors |

T7's mutation was crude and broke the module rather than the behaviour, so it shows coverage
exists but is not surgical evidence. T2, T3 and T6 are clean single-test bites.

## Constraints

Do not bump the version, tag, or touch `main`. Do not reintroduce a `QScrollArea` in the
toolbar. Do not remove `timid = true`, the `pyarrow` import, or the overwrite confirmation.
Do not change `EngineKind` or the sqlglot identifiers in `DIALECT_MAPPING`. Do not alter the
six working features while fixing the test.

## Deferred

Icon legibility at high DPI, row-banding weight, and toolbar composition after the export
move are manual maintainer checks. Filter expressions evaluate against the **preview** frame
only and cannot reach rows excluded by the preview limit.

STATUS: CHANGES_REQUESTED
