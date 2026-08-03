# Review — results-export-and-headers (round 01)

Branch: `feat/results-export-and-headers` @ `0b83305`
Reviewed against: `docs/plans/2026-08-02_results-export-and-headers.md`

## Verdict

CHANGES_REQUESTED — **one defect: the header type badges are computed but never rendered.**
The other five tasks are correct and verified; do not redo them.

## Gate status

```text
ruff check   All checks passed
ty check .   All checks passed
pytest       433 passed, 7 deselected   (was 430; +3 tests)
git status   clean
```

## Required changes

### K1 — the dtype badges are invisible to the user

`_dtype_badge` (`widgets/result_table_view.py:56-70`) maps dtypes correctly to
`INT` / `FLOAT` / `NUM` / `DATE` / `TXT` / `BOOL` / `OTHER`, and
`polars_table_model.py:79-80` returns them — but under **`Qt.ItemDataRole.UserRole`**.
Qt does not paint `UserRole`, and there is no custom header view, no `paintSection`
override, and no header delegate anywhere in `result_table_view.py`.

Measured from a running window with an int/str/date/bool frame:

```text
headerData(DisplayRole)  ['age', 'name', 'when', 'ok']      <- no badge anywhere
headerData(ToolTipRole)  ['age: Int64', 'name: String', 'when: Date', 'ok: Boolean']
```

So the user sees plain column names. This is the same shape as the defect that motivated
the task: an indicator that exists in the data model but never reaches the screen. The
plan asked for badges "rendered as text, not as a generated pixmap" and required the badge
text to be "retrievable from the header ... **alongside the column name**".

**Required change.** Make the badge visible in the header. Either include it in the
`DisplayRole` string (e.g. `age  INT`) or paint it with a `QHeaderView` subclass; the plan
does not mandate which. Whichever you choose, a user looking at the results grid must see
the type without hovering.

**The test must fail against the current code.** Any assertion that reads `UserRole` passes
today while nothing is displayed — that is precisely how this shipped. Assert on what is
rendered: the `DisplayRole` header string containing the badge, or the painted output. Keep
the tooltip assertion as it is; the tooltips are correct.

Note for the negative control: a badge check that compares the *last whitespace-separated
token* of each header will pass on the unfixed code, because column names are already
distinct. My own first probe did exactly that and reported a false pass. Compare the badge
substrings themselves.

## Verified and correct — do not revisit

```text
D1  starter query  main_window.py:609  ->  SELECT * FROM "alias"   (no LIMIT)
    ExecutionRequest default preview_limit = 1000
    SettingsService.DEFAULT_PREVIEW_LIMIT = 1000
D2  export_preview_button / export_full_button / export_selection_button  all absent
    export_button, export_scope_selector, export_format_selector present and visible at 1024px
    Query menu retains Export Preview… / Export Full Results… / Export Selection…
D4  lexer per-style fonts before={0:12, 5:12, 11:12}  after set_font_size(28)={0:28, 5:28, 11:28}
    (the defect was these staying at 9 while defaultFont changed)
D5  preview control is a QLineEdit named preview_limit_selector
    '500'    -> stored 500      '50000'  -> stored 50000
    '5'      -> rejected        '999999' -> rejected
    'abc'    -> rejected        ''       -> rejected
    a rejected value never reaches ExecutionRequest.preview_limit
```

D5's validation is exactly right: every out-of-range and non-numeric input leaves the last
valid setting intact rather than clamping silently or raising.

## Constraints

Do not bump the version, tag, or touch `main`. Do not alter the five working tasks while
fixing the badge rendering. Do not remove the Query-menu export actions, `timid = true`,
the `pyarrow` import, or the overwrite confirmation.

Run the negative controls the plan requires against the **full** suite, and prove each
mutation actually changed the file before trusting its result.

STATUS: CHANGES_REQUESTED
