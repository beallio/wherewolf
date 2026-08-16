# Plan: Filename columns and value-counts chart usability (filename-and-value-counts-ux)

## Context

Three independent user-reported UI defects in the PyQt6 desktop shell. All three
were reproduced by measurement before this plan was written; the measurements are
restated below so you can rebuild them rather than trust them.

### Defect A — the catalog File column still hides the filename

`CatalogModel.data` (`src/wherewolf/desktop/models/catalog_model.py:72`) returns the
full absolute path as `DisplayRole`. Release 0.8.0 attempted to fix this by setting
`textElideMode` to `ElideMiddle` and making section 1 `Stretch`
(`src/wherewolf/desktop/widgets/catalog_dock.py:50-57`). That was a half-fix: the
displayed string is still the whole path, so the column spends its width on the
directory prefix every row shares.

Measured by constructing the real `CatalogDock` offscreen (Sans 9pt) and reading
`header.sectionSize(1)` at several dock widths, against
`C:\Users\dbeall\OneDrive - Contoso\Documents\Analytics\2026\exports\customers.parquet`
and `...\transactions_2026_q1.parquet`:

| Dock width | File section | `customers.parquet` visible | `transactions_2026_q1.parquet` visible |
|---|---|---|---|
| 400 px | 140 px | no | no |
| 450 px | 190 px | no | no |
| 550 px | 290 px | yes | no |
| 700 px | 440 px | yes | yes |

The other three sections consume a fixed 246 px (Alias 100 Interactive, Format 53,
Schema status 93), so the File section only gets what is left. Windows 11 renders
with Segoe UI, which is wider than the Sans 9pt used for these numbers, so the real
thresholds on the reporting user's machine are higher still.

Two further facts, both verified:

- Section 1 is `Stretch`, which makes it **non-interactive** — dragging its edge does
  nothing. The original complaint was "resizing the column changes nothing"; that is
  now literally enforced by the 0.8.0 fix.
- `ElideMiddle` costs roughly double the width it needs to.
  `transactions_2026_q1.parquet` requires a 342 px section before the basename
  survives elision inside the full path; the basename alone renders in 169 px.

The rendering path is **not** broken. Do not go looking for a header or repaint bug;
there isn't one. The defect is that the wrong string is being displayed.

### Defect B — most of the value-counts chart is unreachable

`ValueCountsChart.paintEvent`
(`src/wherewolf/desktop/widgets/value_counts_window.py:55`) computes:

```python
row_height = max(22, (self.height() - padding * 2) // len(self._counts))
```

The default Top N is 50 (`value_counts_window.py:143`), so on first open the widget
paints 50 rows at the 22 px floor — about 1100 px of content — into a chart pane a
few hundred pixels tall. `self.chart` is a bare `QWidget` added straight to the
window's `QVBoxLayout` (`:158-160`); there is no `QScrollArea` anywhere in the file.
Everything past the bottom edge is painted off-widget and cannot be reached by any
user action. The user sees roughly the top eight bars with no indication the rest
exist.

`Top N` accepts values up to 10,000 (`:142`), so the chart must stay cheap at large
N. The agreed approach is to make the chart's full height real and scrollable while
culling the paint loop to the exposed rectangle, so paint cost stays proportional to
what is visible rather than to N.

### Defect C — the Top N spinbox starts a thread per keystroke

`self.limit_selector.valueChanged.connect(self._run_worker)`
(`value_counts_window.py:144`) starts a fresh `ValueCountsWorker` on every value
change. Clicking the up-arrow from 50 to 60 launches ten concurrent scans of the
column; typing `500` launches three. On a large Parquet source this is a visible
stall, and because nothing tracks which worker is current, a slow earlier result can
land after a faster later one and overwrite the correct table.

### Intended outcome

- The catalog table shows the filename in its own column and the parent directory in
  a separate, dimmed, left-elided `Folder` column, with the full path on the tooltip
  of both. The File column is user-resizable.
- The value-counts chart is fully scrollable to the last row at any Top N up to the
  10,000 maximum, and stays responsive at that size.
- Changing Top N issues one query after the user stops adjusting it, and results from
  superseded workers are discarded.

### Design decisions already made

These were settled with the user. Do not revisit them.

- **Separate `Folder` column, not basename-only.** Basename-only would render
  `2025/sales.parquet` and `2026/sales.parquet` identically in the table.
- **A delegate, not just a `ForegroundRole`.** The `Folder` column needs `ElideLeft`
  so the distinguishing tail of the directory survives, and elide mode is a per-view
  property — a per-column override requires a delegate. The delegate handles both the
  dimming and the elide.
- **Scroll to the full row count**, not a capped chart with a "showing top N" notice.
  Paint culling is what makes this affordable.

**Slug used throughout this plan:** `filename-and-value-counts-ux`

---

## Orchestration Contract

**Slug:** `filename-and-value-counts-ux`

**Plan file:**

```text
docs/plans/2026-08-16_filename-and-value-counts-ux.md
```

**Implementation branch:**

```text
feat/filename-and-value-counts-ux
```

**Round-complete marker:**

```text
/tmp/wherewolf/filename-and-value-counts-ux_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/filename-and-value-counts-ux_finalized
```

**Review notes:**

```text
docs/review/filename-and-value-counts-ux-review-*.md
```

Each review note ends with exactly one status trailer:

```text
STATUS: CHANGES_REQUESTED
```

or:

```text
STATUS: APPROVED
```

---

## Required Agent Protocol

1. Use the **implementer** skill.
2. Work from the repository root.
3. Branch from `dev`.
4. Commit this plan as the first commit on the implementation branch.
5. Follow TDD where behavior changes are testable.
6. Run quality gates before marking any round complete.
7. Do not write your own review.
8. Do not create files under `docs/review/`.
9. Do not delete files under `docs/review/`.
10. Review notes are durable audit records and must be committed.
11. Resolving a review note means:
    - implement the requested changes;
    - run quality gates;
    - commit the code/docs changes;
    - commit the review note itself if it is not already committed;
    - recreate the round-complete marker.
12. After finalization, stop polling and exit cleanly.

---

## Scope discipline

- Implement only the units the plan lists. Do not modify files outside the plan's scope.
- Do not change runtime behavior beyond what the plan specifies. A `refactor` or
  `cleanup` commit must preserve observable behavior.
- Never edit a test's expected value to make a behavior change pass. If a test
  legitimately must change, that change must be required by the plan or a review
  note, and you must record the rationale in the session log.
- If you spot an unrelated improvement, do not make it here — note it in the
  session log for a separate plan.

---

## Setup

Start from `dev`:

```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/filename-and-value-counts-ux
```

Commit this plan first:

```bash
git add docs/plans/2026-08-16_filename-and-value-counts-ux.md
git commit -m "docs(plan): add filename-and-value-counts-ux implementation plan"
```

---

## Implementation Tasks

Work the three units in order. Each unit is one or more atomic commits and must be
green before you start the next. Follow Red-Green-Refactor: the failing test comes
first in every case.

### Unit A — Catalog `File` and `Folder` columns

**A1. Widen the model to five columns.**

In `src/wherewolf/desktop/models/catalog_model.py`:

- Change `_COLUMNS` from the current 4-tuple to
  `("Alias", "File", "Folder", "Format", "Schema status")`. Update the
  `ClassVar` type annotation to match the new length (it is currently
  `tuple[str, str, str, str]`; use `tuple[str, ...]`).
- Rewrite the `DisplayRole`/`EditRole` branch in `data()` for the new indices:
  - `0` → `entry.alias`
  - `1` → `entry.path.name`
  - `2` → `str(entry.path.parent)`
  - `3` → `entry.source_format.value`
  - `4` → `self._schema_status_text(entry)`
- Extend the `ToolTipRole` branch so **both** column 1 and column 2 return
  `str(entry.path)`. It currently only covers column 1.
- Leave `flags()` and `setData()` keyed on column 0. Alias editing must not move.

Write the failing test first in `tests/test_catalog_model.py`. Assert
`columnCount() == 5`, that `data(index(0, 1))` is the bare filename with no separator
in it, that `data(index(0, 2))` is the parent directory, and that `ToolTipRole` on
both columns 1 and 2 is the full path.

**A2. Update the existing column-index tests.**

`tests/test_catalog_model.py` and `tests/test_catalog_dock.py` hard-code the old
indices and will fail once A1 lands. These specific updates are **required by this
plan**, so they are not scope violations — record them in the session log anyway:

- `tests/test_catalog_model.py:15` — `columnCount() == 4` becomes `== 5`.
- `tests/test_catalog_model.py:27` — column 1 is now the basename, not the full path.
- `tests/test_catalog_model.py:28` — format moves from column 2 to column 3.
- `tests/test_catalog_model.py:55-57` — schema status moves from column 3 to column 4.
- `tests/test_catalog_dock.py:456` — schema status moves from column 3 to column 4.
- `tests/test_catalog_dock.py:308` — clicking `index(1, 1)` still targets the File
  column; confirm the assertion around it still describes the intended behavior and
  adjust only if the column meaning changed.

Do not weaken any of these assertions. If one cannot be made to pass without removing
what it checks, stop and say so in the session log rather than deleting it.

**A3. Add the folder delegate.**

Create `src/wherewolf/desktop/widgets/folder_column_delegate.py`:

- A module-level pure function `dim_colour(text: QColor, base: QColor, factor: float = 0.55) -> QColor`
  that linearly blends `text` toward `base` by `factor` on each RGB channel. Keep it
  free of any Qt widget dependency so it is unit-testable without a paint pass.
- `class FolderColumnDelegate(QStyledItemDelegate)` overriding `initStyleOption`:
  call `super().initStyleOption(option, index)`, then set
  `option.textElideMode = Qt.TextElideMode.ElideLeft` and replace the option's text
  colour with `dim_colour(option.palette.text().color(), option.palette.base().color())`.
  Apply the dimmed colour to the `Text` and `WindowText` palette roles only. Leave
  `HighlightedText` untouched, so a selected row stays legible against the highlight
  rather than being dimmed into it.
- Export it from `src/wherewolf/desktop/widgets/__init__.py` alongside the existing
  widget exports.

Test first, in a new `tests/test_folder_column_delegate.py`:

- `dim_colour` on a known light and a known dark pair returns a colour strictly
  between the two on each channel, and is idempotent in direction (dimming dark text
  on a light base yields a *lighter* colour; dimming light text on a dark base yields
  a *darker* one). This is the test that proves the delegate works in both themes.
- After `initStyleOption`, `option.textElideMode == Qt.TextElideMode.ElideLeft`.

**A4. Wire the dock.**

In `src/wherewolf/desktop/widgets/catalog_dock.py`:

- Keep `setTextElideMode(Qt.TextElideMode.ElideMiddle)` as the view-wide default; the
  delegate overrides it for the Folder column only.
- Replace the resize-mode block with the new five-column layout:
  - `0` Alias — `Interactive`
  - `1` File — `Interactive`
  - `2` Folder — `Stretch`
  - `3` Format — `ResizeToContents`
  - `4` Schema status — `ResizeToContents`
- Give the File section a usable starting width with
  `header.resizeSection(1, 220)` after the resize modes are set. 220 px comfortably
  fits `transactions_2026_q1.parquet` (measured at 169 px) with headroom.
- Install the delegate: `self._view.setItemDelegateForColumn(2, FolderColumnDelegate(self))`.
  Keep a reference on the instance so it is not garbage-collected.

Test first, in `tests/test_catalog_dock.py`:

- Section 1 is `Interactive` — a `Stretch` section is not user-resizable, and this
  assertion is the one that pins the actual user complaint. Prove it behaviourally as
  well as structurally: call `header.resizeSection(1, 400)` and assert
  `header.sectionSize(1) == 400`. Against `Stretch` that assignment does not stick.
- Section 2 is `Stretch`.
- `view.itemDelegateForColumn(2)` is a `FolderColumnDelegate`.
- At a 450 px dock — the width from the original bug report — the File cell's rendered
  text contains the complete basename. Compute it the same way the existing tests do,
  with `QFontMetrics(view.font()).elidedText(...)` against `header.sectionSize(1) - 8`,
  and assert `path.name in rendered`. Use a long Windows-style path string as the
  fixture so the case that was reported is the case under test.

### Unit B — Scrollable value-counts chart

In `src/wherewolf/desktop/widgets/value_counts_window.py`:

**B1. Give `ValueCountsChart` a real height.**

- Add a class constant `ROW_HEIGHT = 24` and `PADDING = 8`, replacing the local
  `padding = 8` and the `row_height = max(22, ...)` expression. The row height is now
  fixed and never compressed to fit — that compression is the bug.
- In `set_counts`, after storing the counts, call
  `self.setMinimumHeight(len(counts) * self.ROW_HEIGHT + self.PADDING * 2)` and
  `self.updateGeometry()`.
- Implement `sizeHint()` returning
  `QSize(self.width(), len(self._counts) * self.ROW_HEIGHT + self.PADDING * 2)`.
- Keep the existing empty-counts early return so a chart with no data still paints.

**B2. Cull the paint loop to the exposed rectangle.**

`paintEvent` currently iterates every row. Change it to derive the visible span from
the event rect, which is what keeps a 10,000-row chart affordable:

```python
rect = a0.rect() if a0 is not None else self.rect()
first = max(0, (rect.top() - self.PADDING) // self.ROW_HEIGHT)
last = min(len(self._counts) - 1, (rect.bottom() - self.PADDING) // self.ROW_HEIGHT)
```

Then iterate `range(first, last + 1)` and keep using the absolute row index when
computing `top`, so rows land at the same coordinates as before. The `maximum` used
for bar scaling must still be taken across **all** counts, not just the visible slice,
or bar lengths will jump as the user scrolls.

**B3. Put the chart in a scroll area.**

- Import `QScrollArea`. Build it in `__init__`, `setWidgetResizable(True)`,
  `setWidget(self.chart)`, and add the scroll area to the layout in the chart's place.
- Keep `self.chart` pointing at the `ValueCountsChart` itself — existing tests use it.
- Expose the scroll area as `self.chart_scroll_area`.
- The chart's size policy should be `Expanding` horizontally and `Fixed`/`Minimum`
  vertically now that its height is authoritative; `setWidgetResizable(True)` will
  still stretch it horizontally to the viewport.

Test first, in `tests/test_value_counts_window.py`:

- With 50 counts, `chart.minimumHeight()` is at least `50 * ROW_HEIGHT`, and is
  strictly greater than the height of the scroll area's viewport at a normal window
  size. This is the assertion that fails against today's code, where the chart is
  compressed to fit and nothing scrolls.
- The scroll area's vertical scrollbar reports a non-zero `maximum()` with 50 counts
  and a `maximum()` of 0 with 2 counts. A scrollbar that never has anything to scroll
  is the current bug.
- With 10,000 counts, `chart.sizeHint().height()` is the full computed height and a
  `chart.grab()` of a 400 px-tall region still returns without error — the culling
  path must not index out of range at the top or bottom edge.
- Keep the existing `test_value_counts_chart_paints_zero_and_single_rows` passing;
  zero counts and one count are the culling loop's edge cases.

### Unit C — Debounce Top N and discard stale results

In `src/wherewolf/desktop/widgets/value_counts_window.py`:

**C1. Debounce the spinbox.**

- Add `self._limit_debounce = QTimer(self)`, `setSingleShot(True)`, `setInterval(300)`,
  with `timeout` connected to `self._run_worker`.
- Change the spinbox wiring from `valueChanged.connect(self._run_worker)` to
  `valueChanged.connect(self._limit_debounce.start)`.
- The initial load in `__init__` stays a direct `self._run_worker()` call — the first
  render must not wait 300 ms.
- Expose the interval as a class constant `DEBOUNCE_MS = 300` so tests can reference
  it rather than hard-coding a magic number.

**C2. Discard superseded results.**

Nothing currently tracks which worker is current, so a slow early result can overwrite
a fast later one.

- Add `self._current_worker: ValueCountsWorker | None = None`, set to the newly created
  worker at the end of `_run_worker`.
- Connect `result_ready` so the handler can tell which worker produced the result —
  e.g. `worker.result_ready.connect(partial(self._on_result_from, worker))` — and have
  `_on_result_from` return immediately unless `worker is self._current_worker`.
- Keep `_on_result` as the method that actually applies a result to the table and
  chart, so the existing test that calls `window._on_result(...)` directly keeps
  working.
- `closeEvent` must still stop every worker in `self._workers`, not just the current
  one. Do not narrow that cleanup.

Test first, in `tests/test_value_counts_window.py`:

- Rapid changes coalesce: set the spinbox to 10, 20, then 30 in immediate succession,
  wait past `DEBOUNCE_MS`, and assert the fake adapter recorded the initial 50 and
  exactly one follow-up call, for 30. Against today's code this records three
  follow-up calls, so the test fails before the fix.
- A stale result is ignored: drive `_on_result_from` with a worker that is not
  `_current_worker` and assert the table row count is unchanged.
- The existing `test_value_counts_window_reruns_when_limit_changes` uses
  `qtbot.waitUntil`, whose default timeout comfortably exceeds 300 ms, so it should
  keep passing unchanged. If it does not, fix the implementation, not the test.

---

## Quality Gates

Run before marking any round complete:

```bash
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

The round is not complete unless:

1. all requested implementation work is done;
2. all relevant tests pass;
3. build/typecheck gates pass;
4. review notes have not been deleted;
5. the working tree is clean;
6. all code/docs changes are committed.

---

## Verification

Every step below must be able to fail. Before adding any step of your own, answer:
*what state of the world makes this print the failure output?* If the answer is
"none" or "only if the tool is broken", the step is decoration — delete it. Report the
actual output of each command — pass/fail tallies and printed values — not a
conclusion that it passed.

Run everything through the wrapper. Qt needs an offscreen platform in this
environment:

```bash
export QT_QPA_PLATFORM=offscreen
```

### V1 — Prove the gates can fail before trusting them

Before relying on the suite, break one thing and watch it go red.

```bash
./run.sh uv run pytest tests/test_catalog_model.py -x -q
```

Temporarily change `CatalogModel._COLUMNS` to drop the `"Folder"` entry, re-run, and
record the failure output. Restore it and re-run. If the suite passes in both states,
the Unit A tests are not testing what they claim and must be rewritten before you
continue.

### V2 — Reproduce Defect A's measurement, then show it fixed

Write `scripts/verify_catalog_columns.py` (delete it before the final commit; it is a
measurement harness, not a deliverable). It must:

1. Build a real `CatalogDock` with two entries whose paths share a long directory
   prefix and differ only in basename, one of them
   `transactions_2026_q1.parquet`.
2. `dock.resize(450, 200)`, `dock.show()`, `QApplication.processEvents()`.
3. Print `header.sectionSize(i)` for all five sections.
4. For each row, print the File cell's rendered text via
   `QFontMetrics(view.font()).elidedText(basename, view.textElideMode(), header.sectionSize(1) - 8)`
   and whether the full basename is contained in it.
5. Assert the basename is fully visible for **both** rows and exit non-zero with an
   explicit message naming the row that failed if not. Do not print a hardcoded
   success string; print the measured values and let the assertion decide the exit
   code.

Run it and record the output:

```bash
./run.sh uv run python scripts/verify_catalog_columns.py; echo "exit=$?"
```

Expected: exit 0, with both rows showing the complete basename at a 450 px dock — the
width at which the pre-fix build showed neither.

### V3 — Prove the File column is actually draggable

The `Stretch` mode was the reason resizing did nothing, so assert the behaviour, not
just the enum:

```bash
./run.sh uv run pytest tests/test_catalog_dock.py -q -k "resize or interactive or stretch"
```

The test must call `header.resizeSection(1, 400)` and assert `sectionSize(1) == 400`.
Record the tally. A structural-only check that section 1 reports `Interactive` is not
sufficient on its own — see VS-13 in the verification standards.

### V4 — Prove the chart scrolls to the last row

```bash
./run.sh uv run pytest tests/test_value_counts_window.py -q
```

Then a direct check that the chart's height becomes larger than its viewport at the
default Top N, which is what gives the scroll area something to scroll:

```bash
./run.sh uv run python - <<'PY'
from PyQt6.QtWidgets import QApplication

app = QApplication([])
from wherewolf.desktop.widgets.value_counts_window import ValueCountsChart
from wherewolf.desktop.workers.value_counts_worker import ValueCount

chart = ValueCountsChart()
chart.resize(600, 300)
counts = tuple(ValueCount(f"v{i}", 100 - i, 1.0) for i in range(50))
chart.set_counts(counts)

needed = len(counts) * ValueCountsChart.ROW_HEIGHT
print(f"minimumHeight={chart.minimumHeight()} sizeHint={chart.sizeHint().height()}")
print(f"needed_at_least={needed} viewport_height=300")
assert chart.minimumHeight() >= needed, (
    f"chart compressed to {chart.minimumHeight()}px, expected >= {needed}px"
)
assert chart.minimumHeight() > 300, (
    f"chart height {chart.minimumHeight()}px does not exceed the 300px viewport, "
    "so nothing will ever scroll"
)
PY
echo "exit=$?"
```

Expected: exit 0, with `minimumHeight` at least `50 * ROW_HEIGHT` (1200 px at
`ROW_HEIGHT = 24`).

Run this **after** B1 lands. It cannot be run against the pre-fix code, because
`ROW_HEIGHT` does not exist there and the script would die with `AttributeError`
rather than a meaningful assertion failure. The pre-fix behaviour is proved instead by
mutation #4 in V6, which restores the `max(22, ...)` compression and must turn the
chart suite red.

### V5 — Prove the debounce coalesces

```bash
./run.sh uv run pytest tests/test_value_counts_window.py -q -k "debounce or coalesce or stale"
```

Record the tally. The coalescing test must observe exactly one adapter call after
three rapid spinbox changes. Against the pre-fix implementation it observes three.

### V6 — Mutation tests (negative controls)

These run **after** V1–V5 and are the steps that prove the tests are load-bearing
rather than decorative. For each mutation: apply it, run the named suite, record that
it goes **red**, then revert and confirm it goes green again. A mutation that leaves
the suite green means that unit is untested — fix the test before proceeding.

| # | Mutation | Suite that must go red |
|---|---|---|
| 1 | In `catalog_model.py`, return `str(entry.path)` from column 1 instead of `entry.path.name` | `tests/test_catalog_model.py`, `tests/test_catalog_dock.py` |
| 2 | In `catalog_dock.py`, set section 1 back to `QHeaderView.ResizeMode.Stretch` | `tests/test_catalog_dock.py` |
| 3 | In `folder_column_delegate.py`, drop the `option.textElideMode = ElideLeft` line | `tests/test_folder_column_delegate.py` |
| 4 | In `value_counts_window.py`, restore `row_height = max(22, (self.height() - padding * 2) // len(self._counts))` | `tests/test_value_counts_window.py` |
| 5 | In `value_counts_window.py`, reconnect `valueChanged` directly to `_run_worker` | `tests/test_value_counts_window.py` |

Record the red output for each of the five, not just a statement that they failed.

### V7 — Full suite and gates

```bash
scripts/orchestration/run-quality-gates
```

Record the ruff, ty, and pytest tallies as printed. Then confirm the harness script
from V2 is gone and the tree is clean:

```bash
git status --short
```

### Deferred and unverified

State these explicitly in the session log; do not let them read as covered:

- **Windows 11 is not exercised.** Every measurement here runs on Linux with
  `QT_QPA_PLATFORM=offscreen` under Sans 9pt. Win11 renders Segoe UI, which is wider,
  so the pixel thresholds differ. The fix is font-independent — it changes *which
  string* is displayed, not how it is measured — but the reporting user's exact
  rendering is not reproduced by any test in this plan. This defect was reported on
  Win11 and last time it was declared fixed without a Windows check, it was not fixed.
  Flag it for manual confirmation on the reporter's machine before the next release.
- **The delegate's painted output is not pixel-verified.** `initStyleOption` is
  asserted directly; no test compares rendered pixels, so a Qt style that ignores the
  option's palette would not be caught.
- **Scroll performance at Top N = 10,000 is checked for correctness, not speed.** The
  culling test proves no index error and a bounded paint region; it does not measure
  frame time.
- **No test covers a value-counts source large enough for two workers to genuinely
  overlap in wall-clock time.** The stale-result path is verified by driving the
  handler directly, not by racing real queries.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished filename-and-value-counts-ux
```

This writes:

```text
/tmp/wherewolf/filename-and-value-counts-ux_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer filename-and-value-counts-ux`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/filename-and-value-counts-ux-review-*.md
```

When a review note exists or a new review note appears:

1. Read the full review note.
2. If the note ends with:

   ```text
   STATUS: CHANGES_REQUESTED
   ```

   then resume work.

3. Clear the round-complete marker:

   ```bash
   scripts/orchestration/clear-finished filename-and-value-counts-ux
   ```

4. Address every requested change.
5. Run quality gates:

   ```bash
   scripts/orchestration/run-quality-gates
   scripts/orchestration/check-review-notes-not-deleted
   ```

6. Commit code/docs fixes.
7. Commit the review-note file itself if it is not already committed:

   ```bash
   git add docs/review/filename-and-value-counts-ux-review-*.md
   git commit -m "docs(review): record filename-and-value-counts-ux review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished filename-and-value-counts-ux
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer filename-and-value-counts-ux` after the next review note is created.

---

## Approval Handling

If the latest review note ends with:

```text
STATUS: APPROVED
```

then:

1. Confirm every previous review item has been addressed.
2. Confirm all review notes are committed:

   ```bash
   scripts/orchestration/check-review-notes-committed filename-and-value-counts-ux
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize filename-and-value-counts-ux
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/filename-and-value-counts-ux_finalized
   ```

6. Stop polling and exit cleanly.

---

## Review Rules

Do not write your own review.

Do not create files under:

```text
docs/review/
```

Do not delete files under:

```text
docs/review/
```

Only the orchestrator writes review notes. Your job is to read them, resolve them, commit them as audit records, and continue the loop.

---

## Finalization Rules

Only finalize after a review note with:

```text
STATUS: APPROVED
```

Finalization is performed with:

```bash
scripts/orchestration/finalize filename-and-value-counts-ux
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/filename-and-value-counts-ux_finished
/tmp/wherewolf/filename-and-value-counts-ux_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
