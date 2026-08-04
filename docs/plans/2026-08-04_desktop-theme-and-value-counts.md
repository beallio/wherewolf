# Plan: Program theme, live editor previews, schema value counts, and layout fixes (desktop-theme-and-value-counts)

## Context

Third round of desktop UI work, after `2026-08-03_desktop-shell-ui-fixes.md` and
`2026-08-03_desktop-ui-refinements.md` (both merged and released as 0.6.1). Eight
user-requested items. **Two of them are defects in the previous round's work that
its tests wrongly reported as fixed** — read those two carefully, because the
lesson is that a property being set is not the behaviour being delivered.

1. **No application-wide theme.** Only the SQL editor is themed
   (`sql_editor.py:28`); `application.py:10` creates a bare `QApplication` with no
   palette, so the rest of the window always follows the desktop default.
2. **Editor theme changes are not previewable.** `PreferencesDialog`'s
   `editor_theme_selector` has no change-signal connection
   (`main_window.py:140`); the theme is applied only after OK, via
   `dialog.accepted.connect(self._apply_preferences)` (`main_window.py:1110`), so
   a user cannot see a theme before committing to it.
3. **Schema values cannot be copied.** The schema table sets `SelectRows`,
   `ExtendedSelection` and `NoEditTriggers` (`schema_panel.py:80`) but has no
   `Ctrl+C` handler, no clipboard serialization and no context menu.
   `ResultTableView` already implements all three (`result_table_view.py:271`) and
   is the model to follow.
4. **History column reordering does not work — a defect shipped in 0.6.1.**
   `history_dock.py:50` calls only `header.setSectionsMovable(True)`. Qt refuses to
   move a tree's *first* section (it carries the expand indicator) unless
   `setFirstSectionMovable(True)` is also set, and it is not. Verified on the
   installed runtime: `isFirstSectionMovable()` stays `False`. The previous round's
   test asserted `sectionsMovable()` and then dragged a **catalog** column, so it
   passed while the History header stayed frozen.
5. **The toolbars occupy two rows.** `addToolBarBreak(...)` is inserted before the
   second toolbar (`main_window.py:305`), forcing `query_controls_toolbar` onto its
   own row. Both toolbars are movable and floatable by Qt default.
6. **Execution-engine row controls stretch to fill.** No explicit size policies are
   set; `_add_labelled_control` (`main_window.py:398`) only does
   `layout.addWidget(label); layout.addWidget(control)` with zero stretch, so the
   combo boxes' size hints consume the spare width.
7. **The editor's horizontal scrollbar is still broken — a defect shipped in
   0.6.1.** `setScrollWidth(1)` and `setScrollWidthTracking(True)` are set
   (`sql_editor.py:164`), but tracking only ever *grows* the scroll width; nothing
   shrinks it. Reproduced on the installed runtime: after replacing a
   1,000-character line with `SELECT 1`, `SCI_GETSCROLLWIDTH` remained `8453`, so
   the scrollbar stays visible over short text. The existing test
   (`test_sql_editor.py:129`) only covers short→long, which is the direction that
   already worked.
8. **No value-counts view.** `SchemaPanel` has no context-menu policy and no
   `customContextMenuRequested` wiring; its only signals are
   `insert_columns_requested(str)` and `profile_requested(CatalogEntry)`
   (`schema_panel.py:26`).

### Decisions taken by the user

- **Charting: hand-drawn `QPainter`, no new dependency.** Confirmed by inspection
  that nothing charting-capable is available: `PyQt6.QtCharts` is absent
  (`find_spec` returns `None`; it ships as the separate `PyQt6-Charts` package),
  and neither `pyqtgraph` nor `matplotlib` is declared in `pyproject.toml` or
  present in `uv.lock`. Do **not** add a plotting dependency.
- **Program theme offers Light / Dark / Follow system**, defaulting to Follow
  system.
- **Toolbars share one row, and saved layouts are reset** so the change is visible
  to existing installs rather than being masked by restored state.
- **Value counts are Top N with N configurable in the window.**

### Assumption stated, not asked

The program theme and the SQL editor theme stay **independent** settings — the
user asked for both separately, so changing the program theme does not silently
rewrite the editor theme. If that is wrong it is a small follow-up, not a rework.

### Cache-root prerequisite

`/tmp/wherewolf` is already a symlink to `~/.local/state/wherewolf-cache` and
`scripts/check_cache_budget.sh` (4 GiB ceiling) exists. Do not redo that. Run the
budget gate after every task and record the byte count. Note the cache sat at
3.87 GiB during the 0.6.1 release when a `pyspark` source build was attempted
locally — **do not run `uv sync --extra spark`**; the spark configuration is
verified by CI's lint leg, not locally.

**Slug used throughout this plan:** `desktop-theme-and-value-counts`

---

## Orchestration Contract

**Slug:** `desktop-theme-and-value-counts`

**Plan file:**

```text
docs/plans/2026-08-04_desktop-theme-and-value-counts.md
```

**Implementation branch:**

```text
feat/desktop-theme-and-value-counts
```

**Round-complete marker:**

```text
/tmp/wherewolf/desktop-theme-and-value-counts_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/desktop-theme-and-value-counts_finalized
```

**Review notes:**

```text
docs/review/desktop-theme-and-value-counts-review-*.md
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
git checkout -b feat/desktop-theme-and-value-counts
```

Commit this plan first:

```bash
git add docs/plans/2026-08-04_desktop-theme-and-value-counts.md
git commit -m "docs(plan): add desktop-theme-and-value-counts implementation plan"
```

---

## Implementation Tasks

Atomic tasks, in order: one behaviour change, its own tests, its own commit.
TDD — failing test first, record the failure, then implement. Run
`scripts/check_cache_budget.sh` after each task and record the byte count.

**Standing rule for this plan, learned from the two defects above:** a test that
asserts a Qt property was set does not prove the behaviour. Where a task says
"prove the behaviour", the test must exercise the thing a user does — move the
actual section, shrink the actual text, read the actual clipboard — on the widget
in question, not a sibling widget.

Do not run `uv sync --extra spark`. Do not add any plotting dependency.

### Task 1 — Fix History column reordering (defect from 0.6.1)

`history_dock.py:50` needs `header.setFirstSectionMovable(True)` alongside the
existing `setSectionsMovable(True)`.

Test, on the **History** header specifically: assert `isFirstSectionMovable()` is
True, then `moveSection(0, 1)` and assert `visualIndex(0)` actually changed.
Assert both — `sectionsMovable()` alone is what shipped the defect.

Commit: `fix(history): allow the first column to be reordered`.

### Task 2 — Fix the editor's horizontal scrollbar (defect from 0.6.1)

Tracking grows the scroll width but never shrinks it, so the scrollbar persists
after long text is replaced with short text.

Reset the scroll width so it can shrink — setting it back to `1` lets tracking
recompute upward from the current content. Choose where to do that (e.g. on
`textChanged`, or only when the text is replaced wholesale) and **measure the
cost**: a naive reset on every keystroke can cause visible horizontal jitter
while typing mid-line. Record in the session log which trigger you chose, why,
and what you observed about jitter.

Tests, both directions and the regression the old test missed:

- short text → no horizontal scrollbar (existing behaviour, keep it);
- long line → scrollbar appears (existing test, keep it);
- **long line replaced by short text → scrollbar goes away again**, asserted via
  `SendScintilla(SCI_GETSCROLLWIDTH)` shrinking, not only via widget visibility;
- typing additional characters mid-line does not reset the horizontal scroll
  position to zero.

Commit: `fix(editor): shrink scroll width so the h-scrollbar can disappear`.

### Task 3 — Toolbars on one row by default, with saved layouts reset

Remove the `addToolBarBreak(...)` at `main_window.py:305` so both toolbars occupy
one row. Keep them as two separate `QToolBar` objects and leave them movable and
floatable, so they can still be dragged apart.

Restored `saveState()` would otherwise preserve the existing two-row layout
(`main_window.py:1135`) and hide the change. Add a layout-schema version constant,
persist it via `SettingsService`, and skip restoring saved window state when the
stored version is older than the current one (then store the new version). Do not
delete unrelated settings — geometry, splitter sizes, font size and preferences
must survive.

Tests: with no stored layout version, saved toolbar state is not restored and the
version is written; with the current version stored, state *is* restored; a
stale version does not clear geometry/splitter/font settings; both toolbars are
`isMovable()`.

Commit: `feat(desktop): put both toolbars on one row and reset stale layouts`.

### Task 4 — Stop the Execution Engine row from stretching

Constrain the query-controls row so labels and combos take their natural width
instead of filling the toolbar.

Give `engine_selector` and `input_dialect_selector` a size policy that does not
grow (and/or a maximum derived from their longest item via `QFontMetrics` — do
not hardcode pixels), keep the existing font-metrics maximum on
`preview_limit_selector` (`main_window.py:349`), and add a trailing stretch so
spare width collects at the end of the row rather than inside the controls.

Test: assert each control's rendered width is close to its `sizeHint().width()`
after laying the window out at a wide size (e.g. 1600px), rather than growing with
the window. Assert the relationship, not a fixed pixel count.

Commit: `fix(desktop): stop query controls stretching to fill the toolbar`.

### Task 5 — Select and copy in the schema panel

Mirror `ResultTableView`'s mechanism (`result_table_view.py:271`): an overridden
`keyPressEvent` matching `QKeySequence.StandardKey.Copy`, a `copy_selection()`
that serialises the selection to TSV via the existing
`desktop/clipboard_serializers.py` helpers, and a right-click context menu with
Copy. Reuse those serializers — do not write a second TSV formatter.

Keep `NoEditTriggers`; this is copy-only, the schema is not editable.

Tests: selecting rows and pressing Ctrl+C puts the expected TSV on
`QApplication.clipboard()`; the context menu exposes Copy and it copies the same
text; copying with an empty selection does nothing and does not raise.

Commit: `feat(schema): allow selecting and copying schema values`.

### Task 6 — Live editor-theme preview in Preferences

Connect `editor_theme_selector.currentTextChanged` so the editor re-themes as the
selection changes, and revert to the theme that was active when the dialog opened
if the user cancels. OK keeps the previewed theme.

Capture the original theme name on dialog open. On `rejected`, restore it. Make
sure `_apply_preferences` (`main_window.py:1110`) does not double-apply.

Also add at least two further themes to `SqlEditor.THEME_NAMES`
(`sql_editor.py:28`) beyond the current five, each defining **every** colour key
the existing themes define — a partial theme that silently falls back is a defect.

Tests: changing the selector without accepting re-themes the editor immediately;
cancelling restores the pre-dialog theme; accepting keeps the previewed one and
persists it; every name in `THEME_NAMES` applies and yields a distinct paper
colour.

Commit: `feat(editor): preview themes live and add more of them`.

### Task 7 — Application-wide Light / Dark / Follow system theme

Add a program theme independent of the editor theme.

- New module (e.g. `src/wherewolf/desktop/theming.py`) exposing the three modes
  and building a `QPalette` for Light and Dark. Use the Fusion style so the
  palette is honoured consistently across platforms.
- Follow system: resolve the desktop's scheme via Qt's colour-scheme reporting;
  if unavailable, fall back to Light rather than raising.
- Persist the mode through `SettingsService` and add a selector to
  `PreferencesDialog` beside the editor theme selector.
- Apply at startup in `application.py:10` **before** `MainWindow` is constructed,
  and re-apply when the preference changes, without requiring a restart.
- Ensure the results grid's alternating-row colours stay distinguishable under
  both palettes — the existing rule only overrides `AlternateBase` when it equals
  `Base`.

Tests: each mode produces the expected `Window`/`Base` colours; Follow system
resolves to a valid mode and falls back to Light when the scheme is unknown; the
mode round-trips through settings; changing it updates the live application
palette; `AlternateBase != Base` under both Light and Dark.

Commit: `feat(desktop): add a Light/Dark/Follow-system application theme`.

### Task 8 — Value counts from the schema panel

Right-clicking a column row in the schema panel offers **Value counts**, opening a
non-modal floating window for that column.

- Add a context-menu policy and `customContextMenuRequested` wiring to
  `SchemaPanel` (it currently has neither) and a new signal carrying the entry and
  the selected column name.
- Compute counts on a **background worker**, following the existing
  `ProfileWorker` pattern in `desktop/workers/` — do not block the UI thread. The
  query is `SELECT <col>, count(*) FROM <alias> GROUP BY 1 ORDER BY 2 DESC LIMIT
  :n`, built with the existing identifier-quoting helper. Never string-format a
  column name into SQL unquoted.
- The window shows: a spin box for **N** (default 50) that re-runs on change; a
  table of value/count/percentage; a horizontal bar chart drawn with `QPainter`;
  and the total distinct count so the user knows what the Top N omits.
- The table supports selection and Ctrl+C/context-menu copy, reusing the same
  serializers as Task 5.
- The chart is a custom `QWidget` overriding `paintEvent`. It must read its
  colours from the widget palette so it works under both program themes, handle
  zero rows without dividing by zero, and elide long labels.

Tests: right-click emits the signal with the right column; the worker produces
counts ordered descending and honours the limit; changing N re-runs with the new
limit; the chart widget paints without error at several sizes including zero rows
and a single row; copy from the table yields the expected TSV; a column name
containing a double quote is quoted safely and does not break the query.

Commit: `feat(schema): add a value-counts window with a bar chart`.

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

Standards live at
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`
(not in this repo). Comply; do not restate. Every step must be able to fail.
Report actual output, not conclusions.

### V1 — Cache budget after every task

```bash
scripts/check_cache_budget.sh; echo "exit: $?"
```

Record the byte count after each of tasks 1-8. Do not run
`uv sync --extra spark`; that build took the cache to 97% of budget during the
0.6.1 release.

### V2 — Behaviour probes for the two shipped defects

These two regressed *through* a passing test suite, so prove them directly and
record the raw values.

1. **History first column.** Print `isFirstSectionMovable()` before and after the
   fix; move section 0 and print `visualIndex(0)` either side. Both must change.
2. **Editor scroll width.** Print `SendScintilla(SCI_GETSCROLLWIDTH)` after
   setting a 1,000-character line, then again after replacing it with `SELECT 1`.
   The second value must be dramatically smaller. Record both integers — a
   visibility-only assertion is what missed this the first time.

### V3 — Mutation controls

Revert each immediately after recording. Each must turn the named test red; note
the node id and assertion message.

1. Drop `setFirstSectionMovable(True)` → Task 1 History move test fails.
2. Remove the scroll-width reset → Task 2 long→short test fails.
3. Restore `addToolBarBreak` → Task 3 single-row test fails.
4. Remove the trailing stretch / size policy → Task 4 width test fails.
5. Break the schema `copy_selection` serialisation → Task 5 clipboard test fails.
6. Disconnect `currentTextChanged` → Task 6 live-preview test fails.
7. Force the theme resolver to always return Light → Task 7 Dark palette test
   fails.
8. Ignore the spin box's N → Task 8 limit test fails.

### V4 — Negative control (runs last)

After every mutation is reverted:

```bash
./run.sh uv run pytest
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check .
```

Record pytest's summary line verbatim and all four exit statuses. Note that
`ruff format --check` is what CI runs; the local quality-gates hook runs
`ruff format .`, which rewrites instead of failing, so the hook alone will not
catch formatting drift.

### V5 — No new dependency

```bash
git diff dev...HEAD -- pyproject.toml uv.lock
```

Confirm no plotting library was added. The chart is `QPainter`-only. If
`pyproject.toml` dependencies changed at all, justify it in the session log.

### V6 — Manual GUI verification (DEFERRED, not performed by the implementer)

Requires a real display and window manager. State as deferred; do not claim done.

- Dragging the History Timestamp column by mouse.
- The editor scrollbar visually disappearing when long text is deleted.
- Both toolbars sharing one row on first launch, and still being draggable apart.
- Live theme preview while scrolling the Preferences combo.
- The application palette actually following the desktop's dark mode.
- The value-counts chart's readability at small window sizes.

### Explicitly not verified

- The `--extra spark` configuration is not exercised locally; CI's lint leg is
  the only check for it.
- Offscreen rendering does not reproduce real compositor scrollbar behaviour —
  this is why item 7 was wrongly reported fixed. Scroll-width assertions must use
  `SCI_GETSCROLLWIDTH` rather than widget visibility.
- No performance measurement of value counts on very large datasets; the query is
  bounded by the Top N limit but the `GROUP BY` still scans the source.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished desktop-theme-and-value-counts
```

This writes:

```text
/tmp/wherewolf/desktop-theme-and-value-counts_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer desktop-theme-and-value-counts`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/desktop-theme-and-value-counts-review-*.md
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
   scripts/orchestration/clear-finished desktop-theme-and-value-counts
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
   git add docs/review/desktop-theme-and-value-counts-review-*.md
   git commit -m "docs(review): record desktop-theme-and-value-counts review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished desktop-theme-and-value-counts
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer desktop-theme-and-value-counts` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed desktop-theme-and-value-counts
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize desktop-theme-and-value-counts
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/desktop-theme-and-value-counts_finalized
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
scripts/orchestration/finalize desktop-theme-and-value-counts
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/desktop-theme-and-value-counts_finished
/tmp/wherewolf/desktop-theme-and-value-counts_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
