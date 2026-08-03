# Review — ui-legibility (round 01)

Branch: `feat/ui-legibility` @ `a8b853c`
Reviewed against: `docs/plans/2026-08-02_ui-legibility.md`

## Verdict

APPROVED. Three tasks, three commits plus a docs commit.

## U1 — line-number margin

Sizing now comes from digit glyphs (`digit_width + padding`) rather than space
characters. Measured on a running window:

```text
5 lines    margin 18px >= 9px  needed (1 digit)
50 lines   margin 27px >= 18px needed (2 digits)
500 lines  margin 36px >= 27px needed (3 digits)
after _apply_font_size(20)   margin 61px >= 46px needed
```

The inequality holds as the document grows and after a font-size change, which was the
actual requirement. Reported as fixed in the maintainer's hands already — they installed
`7922b66` mid-round and confirmed the margin at 28px against 21px needed.

## U2 — schema panel names its dataset

`schema_panel.py:148` now renders `f"{alias} — {len(columns)} columns"`, and switching
datasets updates it:

```text
headers: ['customers — 2 columns', 'loans — 2 columns']
```

The second half matters: a header written once and never refreshed would have passed a
single-alias check.

## U3 — toolbar controls

All six carry captions and tooltips, via a shared `_add_labelled_control` helper that also
sets a buddy label — so the caption is attached to the control rather than positioned near
it by luck:

```text
engine_selector              'Choose where the query runs: DuckDB or Spark.'
input_dialect_selector       'Choose the SQL dialect you are writing; it is transpiled to the execution engine.'
translation_target_selector  'Choose the SQL dialect rendered in the Translation tab.'
export_format_selector       'Choose the file format for exported query results.'
editor_theme_selector        'Choose the colour theme used by the SQL editor.'
preview_limit_selector       'Choose the maximum number of rows shown in a query preview.'
```

The engine/input-dialect wording resolves the specific confusion the maintainer reported —
three unlabelled dropdowns where one picks *where it runs* and two pick *dialects*.

## Negative controls

| mutation | full suite |
|---|---|
| restore `" " * width` margin sizing | 1 failed, 400 passed |
| drop the alias from the schema header | 1 failed, 400 passed |
| blank the shared tooltip helper | 1 failed, 400 passed |

Baseline is 401 passed, so each mutation costs exactly one test.

**A correction to my own process, recorded because it nearly produced a false finding.**
My first pass ran each mutation against the test file I *guessed* was relevant
(`test_sql_editor.py`, `test_schema_panel.py`) and all of them passed — which reads as
"these fixes have no guard at all". They do: the round added
`tests/test_ui_legibility_line_margin.py`, `_schema.py` and `_toolbar.py`, none of which
my subset invocations touched. A third mutation failed to apply because tooltips are set
through a shared helper rather than per-control, so its "pass" was meaningless too. The
table above is from full-suite runs. **Scope a mutation run to the whole suite, or verify
the mutation both applied and was covered.** This is the second time in this session that
a mutation which did not run looked like a mutation which did not matter.

## Gates

```text
ruff check          All checks passed
ty check .          All checks passed
pytest              401 passed, 7 deselected   (was 398; +3 tests)
git status --short  clean
```

## The boundary held

Version `0.5.2`, no tag, `main` untouched. `pyarrow` import, `timid = true`,
`DIALECT_MAPPING` and `EngineKind` all unchanged.

## Deferred

Whether the toolbar *looks* well composed, how the margin styling reads against the dark
theme, and caption placement are manual maintainer checks — the tests prove the digits
have room and the controls carry text, not that the layout is good.

STATUS: APPROVED
