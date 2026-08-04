# Review — desktop-theme-and-value-counts (round 01)

Branch: `feat/desktop-theme-and-value-counts`
Reviewed against: `docs/plans/2026-08-04_desktop-theme-and-value-counts.md`
Reviewed at: `c0f44e3bdc57a20052b7aa01963c8480c7fa1b47`

## Verdict

All eight tasks are implemented as separate conventional commits in plan order.
Both defects carried over from 0.6.1 are genuinely fixed — I verified them with
the raw before/after values the plan's V2 demanded, not with property
assertions. The value-counts feature works end to end and its numbers are
arithmetically correct.

One finding blocks, and it is a case of the letter of the task being met while the
user's actual complaint survives.

## Gate status

Independently re-run:

- `./run.sh uv run pytest` → **490 passed, 7 deselected**, exit 0
- `./run.sh uv run ruff check .` → exit 0
- `./run.sh uv run ruff format --check .` → exit 0 (the CI form, not the hook's rewriting form)
- `./run.sh uv run ty check .` → exit 0
- `scripts/check_cache_budget.sh` → exit 0, `3457666803` bytes (80% of ceiling — see observations)

**V5, no new dependency:** `git diff dev...HEAD -- pyproject.toml uv.lock` is
empty, and no `pyqtgraph`/`matplotlib`/`QtCharts` import exists anywhere. The
chart is `QPainter`-only as instructed.

## V2 — the two 0.6.1 defects, verified with raw values

Both previously passed a green suite while broken, so these were measured
directly on the running widgets:

```
PROBE 1  History first column
  sectionsMovable       : True
  isFirstSectionMovable : True          <- was False; this was the defect
  visualIndex(0): 0 -> 1   MOVED=True   <- on the History header, not a sibling

PROBE 2  Editor scroll width
  after a 1000-char line : 8453
  after 'SELECT 1'       : 67           <- was still 8453; this was the defect
  SHRANK=True (ratio 0.0079)

PROBE 3  Toolbars
  'Primary'        y=22  movable=True
  'Query Controls' y=22  movable=True
  distinct y positions: {22} -> SAME ROW
```

## Other tasks verified live

- **Task 5 (schema copy):** Ctrl+C with focus in the schema table yields
  `'id\tBIGINT\tUnknown\t1\t...'` on the clipboard. My first probe reported an
  empty clipboard; that was my error — I had selected a row in a panel whose
  schema had not finished loading, so the selection was empty and the
  `if text:` guard correctly declined to write. The mechanism is sound.
- **Task 6 (live preview):** 7 themes now. Selecting `Light` in the open dialog
  changes the editor paper `#1e1e1e → #ffffff` immediately; Cancel restores
  `#1e1e1e`. Correct.
- **Task 7 (program theme):** `ThemeMode` is `LIGHT/DARK/FOLLOW_SYSTEM`;
  `apply_program_theme` sets the Fusion style *and* the palette, and
  `application.py` calls it before `MainWindow` is constructed. Sampled pixels
  under Dark: menubar `#2b2b2b`, results area `#1e1e1e`, status bar `#2b2b2b`.
  `AlternateBase != Base` under both palettes. On the real path — persisted
  `Dark`, open Preferences, preview `Light`, Cancel — the app correctly returns
  to `#2b2b2b` and the persisted value is unchanged.
- **Task 8 (value counts):** against a generated 200-row file whose regions cycle
  `[west,east,north,south,west,west,east]`, the window reported west 85, east 57,
  north 29, south 29 — exactly the expected 3/7, 2/7, 1/7, 1/7 split. Bar lengths
  are proportional, Top N spin box and total-distinct label are present, and the
  SQL uses `quote_identifier` for both column and alias with a parameterised
  `LIMIT ?`.

## Required changes

### Finding 1 (blocking) — the Execution engine combo is still a quarter of the window

Task 4's stated goal was that the query controls stop expanding to fill the
toolbar. Measured at a 1600px window width:

```
engine_selector        width=414  sizeHint=414  ratio=1.00
input_dialect_selector width=95   sizeHint=95   ratio=1.00
preview_limit_selector width=57   sizeHint=108  ratio=0.53
```

So the layout no longer stretches anything — ratio 1.00 means each control sits
at its own size hint. By that measure the task passes, and the test asserting
`width ≈ sizeHint` passes with it.

But the user's complaint was that the row eats the window, and it still does.
`engine_selector`'s *own* size hint is 414px, because one of its items is a
sentence:

```
[0] 'DuckDB'
[1] 'Spark (unavailable: pyspark is not installed; install wherewolf[spark])'
```

That item is 71 characters, 383px of text (`main_window.py:334-339`), and
`_set_selector_natural_width` faithfully sizes the combo to its longest entry.
The result is a combo occupying **26% of a 1600px window** to display the word
"DuckDB".

The test cannot catch this: `width ≈ sizeHint` holds no matter how large
`sizeHint` becomes. It measures the wrong property — the same shape of mistake as
the two defects this plan exists to fix.

Required:

- keep the unavailability *reason* out of the item label. Put it in the item's
  `ToolTipRole` (and/or a short `(unavailable)` suffix), so the combo's natural
  width is driven by `DuckDB` / `Spark`, not by an installation hint;
- the item must stay visibly disabled and the reason must remain discoverable —
  do not simply delete the information;
- add an assertion that bounds the width in absolute terms, not just relative to
  `sizeHint`: e.g. `engine_selector.sizeHint().width()` is under ~150px, or under
  some multiple of the width of its longest *engine name*. Record the measured
  value in the session log;
- re-measure all three controls at a 1600px window and record the table above
  with the new numbers.

## Non-blocking observations

1. Schema copy emits trailing empty fields for unpopulated profile columns —
   `'id\tBIGINT\tUnknown\t1\t\t\t\t\t'`. Faithful to the table, but a user pasting
   into a spreadsheet gets five blank columns. Consider trimming trailing empties.
2. The editor theme reverts on Cancel to the *pre-dialog applied* theme, while the
   program theme reverts to the *persisted* theme. These coincide in normal use,
   so nothing is broken; noting the asymmetry so a future change does not assume
   they behave identically.
3. Cache is at 3.46 GB, 80% of the 4 GiB ceiling and climbing across rounds
   (3.20 → 3.46 in one round). Not yet a problem; worth pruning before the next
   plan rather than during one.

## Confirmed sound

- no review notes deleted; working tree clean apart from the user's pre-existing
  untracked `feature-ideation-workbench-depth.md`;
- test count 462 → 490;
- value-counts SQL is injection-safe: identifiers quoted, limit parameterised, and
  `tests/test_registry.py:104` covers a column name requiring quoting;
- the chart guards zero rows (`if not self._counts: painter.end()`) and zero
  maximum (`... if maximum else 0`), so it cannot divide by zero.

STATUS: CHANGES_REQUESTED
