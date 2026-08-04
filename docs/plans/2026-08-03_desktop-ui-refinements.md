# Plan: Desktop UI refinements: export modal, themes, column control, and dialect help (desktop-ui-refinements)

## Context

A second round of desktop UI work, following `2026-08-03_desktop-shell-ui-fixes.md`
(already merged into `dev`). Nine items, all user-requested. Three of them are
partly built already — extend what exists rather than rebuilding it.

1. **`Quit` has an unreachable shortcut.** `QKeySequence.StandardKey.Quit` was
   verified live on this platform and resolves to `Key_Exit` (keycode 16908298)
   with no modifier — a dedicated hardware key virtually no PC keyboard has.
   `QKeySequence("Ctrl+Q")` reports `NoMatch` against it. The menu therefore
   advertises a shortcut that cannot be pressed (`main_window.py:938`).
2. **The preview-rows input is far too wide.** It is a bare `QLineEdit` with a
   `QIntValidator(10, 100000)` and no width constraint or size policy
   (`main_window.py:292`), so it stretches across the toolbar for a value that is
   at most six digits.
3. **Export options clutter the results page.** `export_format_selector`
   (`main_window.py:798`), `export_scope_selector` (`main_window.py:813`) and
   `export_button` (`main_window.py:825`) sit inline above the grid, permanently
   occupying a row for a rarely-used action.
4. **Manual profiling is unverified on large datasets.** `profile_max_bytes`
   gates *automatic* add-time profiling only (`main_window.py:652`); the Profile
   button queues a `ProfileWorker` directly with no size check
   (`main_window.py:377`). The intended behavior therefore already appears
   correct but has never been tested — this is a verification task, and becomes a
   fix task only if the tests find otherwise.
5. **The results grid has no row striping**, making wide rows hard to track
   across (`result_table_view.py`).
6. **Column reordering is inconsistent.** `setSectionsMovable(True)` is set on
   the results grid (`result_table_view.py:29`) but on none of the other three
   tabular views: catalog (`catalog_dock.py:46`), schema (`schema_panel.py:61`),
   history (`history_dock.py:45`).
7. **The SQL editor's horizontal scrollbar misbehaves.** `WrapNone` is set
   (`sql_editor.py:161`) but neither `setScrollWidth` nor
   `setScrollWidthTracking` is configured. QScintilla defaults to a fixed
   scroll width, so the horizontal scrollbar appears regardless of whether the
   text actually overflows, and does not track content as it changes.
8. **Only two editor themes exist.** `THEME_NAMES = ("Dark", "Light")`
   (`sql_editor.py:28`). The selection mechanism, persistence
   (`settings_service.py:201`) and startup restore (`sql_editor.py:62`) all work
   — the set of themes is simply small.
9. **Help offers no dialect documentation.** The Help menu has About,
   Documentation, and Open-Source Licenses (`main_window.py:1017`), with
   Documentation opening the project README (`main_window.py:1022`). The app
   transpiles across many sqlglot dialects, and there is no route to any of those
   dialects' own reference material.

Out of scope: an application-wide (non-editor) Qt palette. Item 8 is explicitly
about *SQL editor* themes. Note for the record that no app-wide theme exists
(`application.py:10`) and the repo contains no committed screenshot renderer —
the dark README image in commit `66dc510` was produced by an uncommitted
offscreen capture that applied a Fusion dark palette. Neither is addressed here.

### Cache-root prerequisite

`/tmp/wherewolf` is already a symlink to `~/.local/state/wherewolf-cache`, and
`scripts/check_cache_budget.sh` (4 GiB ceiling) exists from the previous plan. Do
**not** re-do that relocation. Run the budget gate after every task and record the
byte count, exactly as the previous plan required. If the gate reports
`cache root is not a symlink`, stop and report rather than working around it.

**Slug used throughout this plan:** `desktop-ui-refinements`

---

## Orchestration Contract

**Slug:** `desktop-ui-refinements`

**Plan file:**

```text
docs/plans/2026-08-03_desktop-ui-refinements.md
```

**Implementation branch:**

```text
feat/desktop-ui-refinements
```

**Round-complete marker:**

```text
/tmp/wherewolf/desktop-ui-refinements_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/desktop-ui-refinements_finalized
```

**Review notes:**

```text
docs/review/desktop-ui-refinements-review-*.md
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
git checkout -b feat/desktop-ui-refinements
```

Commit this plan first:

```bash
git add docs/plans/2026-08-03_desktop-ui-refinements.md
git commit -m "docs(plan): add desktop-ui-refinements implementation plan"
```

---

## Implementation Tasks

Each task is atomic: one behavior change, its own tests, its own commit, in
order. Follow TDD — write the failing test first, run it, record the failure,
then implement. After every task run `scripts/check_cache_budget.sh` and record
the printed byte count in the session log as an ordered list.

Several existing tests assert menu structure, shortcuts, and the results-page
layout. Where a task authorizes updating one, that update is required by this
plan. Do not edit any other test's expected values.

### Task 1 — Give Quit a reachable shortcut

`main_window.py:938` sets `QKeySequence.StandardKey.Quit`, which resolves to
`Key_Exit` here. Replace it so the action is actually reachable:

- set the primary shortcut to `QKeySequence("Ctrl+Q")`;
- keep the platform standard key as an *additional* binding via
  `setShortcuts([QKeySequence("Ctrl+Q"), QKeySequence(QKeySequence.StandardKey.Quit)])`
  so platforms where the standard key is sensible keep it.

Test: assert `Ctrl+Q` is among `quit_action.shortcuts()`, and assert triggering
the action closes the window. Assert specifically that
`QKeySequence("Ctrl+Q").matches(...)` finds an exact match against one of the
action's shortcuts — do not assert merely that the shortcut list is non-empty,
since the pre-fix code also had a non-empty list.

Also fold in these three carried-over cleanups from the previous plan's reviews:

- `closeEvent` reports a shutdown timeout through `self._show_status(...)`
  (`main_window.py:1131`), which is invisible on a closing window. Either drop the
  message or route it somewhere durable; state which you chose and why;
- `CatalogDock.add_paths` emits `datasets_added` *and* `error_reported`, and
  `_handle_add_result` also surfaces `result.warnings`, so a warning is pushed to
  the status bar twice. Make it once;
- `NeverFinishesWorker` (`tests/test_main_window.py:1299`) overrides
  `__getattribute__` to swap in `_fake_wait`. Replace with a plain `wait`
  override if that satisfies ty; if it does not, leave it and say so.

Commit: `fix(desktop): make the Quit shortcut reachable`.

### Task 2 — Constrain the preview-rows input width

The value is at most six digits (`QIntValidator(10, 100000)`,
`main_window.py:292`). Set a maximum width sized from the font rather than a
magic pixel count — measure with `QFontMetrics.horizontalAdvance("100000")` plus
padding, and apply via `setMaximumWidth`.

Test: assert `maximumWidth()` is less than the default `sizeHint().width()` of an
unconstrained `QLineEdit`, and that the widget still accepts and validates
`100000`. A test that only asserts some fixed pixel number would pass against a
wrong value; assert the relationship.

Commit: `feat(desktop): constrain the preview row limit input width`.

### Task 3 — Move export options into a modal

Replace the inline export row with a single button that opens a modal.

- Remove `export_format_selector` and `export_scope_selector` from the results
  page layout (`main_window.py:798`, `813`). Keep `export_button`.
- Add an `ExportOptionsDialog` beside the existing `PreferencesDialog` and
  `FindReplaceDialog` in `main_window.py`, carrying the same format choices (CSV,
  Excel, Parquet) and scope choices (Preview, Full results, Selection), with
  OK/Cancel.
- The dialog must preselect the last-used format and scope so repeat exports do
  not require re-picking. Persist them through `SettingsService` alongside the
  existing preferences.
- `export_button` opens the dialog; accepting it runs the export that the
  previous inline controls would have run.
- The three `QAction`s (`Export Preview…`, `Export Full Results…`,
  `Export Selection…`, `actions.py:61`) must keep working and must keep bypassing
  the dialog — they already name their scope.

Watch for a regression: `_export_selected_scope` and `_start_export` currently
read the combo boxes directly. Every such read must be rerouted, or export will
silently use a stale or default scope.

Tests: the dialog opens on button click; accepting with a chosen format/scope
invokes the export path with those values; cancelling exports nothing; the three
scope actions still export without opening the dialog; the chosen format and
scope survive a dialog reopen.

Authorized to update existing tests that assert the presence of
`export_format_selector` or `export_scope_selector` in the results layout.

Commit: `feat(desktop): collapse export options into a modal`.

### Task 4 — Verify manual profiling, including on large datasets

This is a **verification** task. Implement nothing unless a test fails.

Establish by test that:

- clicking Profile in `SchemaPanel` queues a `ProfileWorker` and the resulting
  `ProfileResult` reaches the panel (`schema_panel.py:53`, `114`;
  `main_window.py:377`);
- a dataset whose size exceeds `restore_profile_max_bytes()` is **not**
  auto-profiled on add, and `mark_profile_skipped` records the reason
  (`main_window.py:652`, `catalog_service.py:177`);
- that same over-limit dataset **is** profiled when the Profile button is used,
  i.e. the size gate does not apply to manual profiling.

The third assertion is the point of the task. Construct the over-limit case by
lowering `profile_max_bytes` via the settings service rather than by generating a
genuinely large file — do not write large fixtures, the cache budget is shared.

If any assertion fails, fix the behavior so manual profiling is ungated, and say
so in the session log.

Commit: `test(profile): cover manual profiling of over-limit datasets`.

### Task 5 — Alternating row colors in the results grid

Enable `setAlternatingRowColors(True)` on `ResultTableView`
(`result_table_view.py`). Verify the alternate color is actually distinguishable
under the active palette rather than assuming the default is visible — if the
palette's `AlternateBase` equals `Base`, set an explicit `AlternateBase` on the
view's palette.

Test: assert `alternatingRowColors()` is True **and** that the palette's
`AlternateBase` differs from `Base`. The second assertion is what makes this more
than a property echo.

Commit: `feat(results): alternate row colors in the results grid`.

### Task 6 — Movable columns in the remaining tabular views

Enable header section movement where it is missing:

- catalog table (`catalog_dock.py:46`);
- schema table (`schema_panel.py:61`);
- history tree header (`history_dock.py:45`).

Leave the results grid alone — it already has it (`result_table_view.py:29`).

Test: one parameterised test asserting `sectionsMovable()` is True for all four
headers, so the results grid guards against regression too. Then actually move a
section with `moveSection(0, 1)` on one of the newly-enabled views and assert
`visualIndex` changed — a property that is set but on a header the user cannot
reach would still pass a property-only check.

Commit: `feat(desktop): allow column reordering in catalog, schema and history`.

### Task 7 — Fix SQL editor horizontal scrolling

`sql_editor.py:161` sets `WrapNone` but never configures the scroll width, so
QScintilla uses a fixed default and shows a horizontal scrollbar whether or not
the text overflows.

Set `setScrollWidth(1)` and `setScrollWidthTracking(True)` so the scroll range
follows actual content: no horizontal scrollbar for short text, one that appears
and sizes correctly once a line exceeds the viewport.

Test: with short text, assert the horizontal scrollbar is not visible; after
setting a line far wider than the viewport, assert it becomes visible. Drive this
through the real widget with an explicit size; do not assert on
`setScrollWidth` having been called.

Commit: `fix(editor): track scroll width so the h-scrollbar reflects content`.

### Task 8 — Add SQL editor color themes

`THEME_NAMES` currently holds `("Dark", "Light")` with five colors each
(`sql_editor.py:28`). Add at least three more complete themes — suggested:
`Solarized Dark`, `Solarized Light`, `High Contrast`. Each must define every
color key the existing two define; a partial theme that falls back silently is a
defect.

`set_theme()` already ignores unknown names (`sql_editor.py:226`) and persistence
already works (`settings_service.py:201`) — do not rework those.

Tests: every name in `THEME_NAMES` applies without error and yields a distinct
paper/background color from the others; a theme selected in Preferences survives
a settings round-trip; an unknown theme name still falls back rather than raising.

Commit: `feat(editor): add additional SQL editor color themes`.

### Task 9 — Help submenu linking to SQL dialect documentation

Add a submenu under Help (`main_window.py:1017`) — a `QMenu` added to
`help_menu`, which is what "collapsible section" means in a Qt menu bar — titled
`SQL Dialect Reference`, containing one action per major dialect, each opening
that dialect's official documentation via `webbrowser.open`, matching how
`documentation_action` already works (`main_window.py:1022`).

Cover at minimum: DuckDB, PostgreSQL, Oracle, MySQL, Microsoft T-SQL, SQLite,
Spark SQL. Prefer dialects the app can actually transpile — cross-check against
the sqlglot dialect list the translation panel offers and note any you include
that the app does not support.

Do not hardcode the URLs inline in `_build_menus`. Put them in a module-level
mapping so they are testable and editable in one place.

Tests: the submenu exists under Help and is a `QMenu`; it contains an action per
entry in the mapping; triggering one calls `webbrowser.open` with that dialect's
URL (monkeypatch `webbrowser.open` — **do not** open a real browser in tests);
every URL is https and non-empty.

Commit: `feat(desktop): add SQL dialect reference links under Help`.

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

Verification standards live at
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`
(not in this repo). Comply with them; do not restate them. Every step must be
able to fail. Report actual output — tallies, byte counts, error strings — not
the conclusion that something worked.

### V1 — Cache budget after every task

```bash
scripts/check_cache_budget.sh; budget_status=$?
echo "cache budget exit: $budget_status"
```

Record the byte count after each of tasks 1-9 as an ordered list. Report a
climbing trend even if the gate never trips.

### V2 — Mutation controls

Run after implementation is complete. Revert each mutation immediately after
recording. Each must turn the named test **red**; a green suite after a mutation
means that task's tests do not test it.

1. Restore `StandardKey.Quit` as the sole shortcut → Task 1 `Ctrl+Q` match test
   fails.
2. Remove the `setMaximumWidth` call → Task 2 width test fails.
3. Make the export dialog return its defaults instead of the chosen values →
   Task 3 chosen-format/scope test fails.
4. Apply `profile_max_bytes` to the manual profile path → Task 4 over-limit
   manual-profile test fails.
5. Set `setAlternatingRowColors(False)` → Task 5 test fails.
6. Remove `setSectionsMovable(True)` from the schema table only → Task 6
   parameterised test fails **and names the schema header**, not just "a header".
7. Remove `setScrollWidthTracking(True)` → Task 7 short-text test fails.
8. Truncate one new theme to a subset of color keys → Task 8 completeness test
   fails.
9. Point one dialect URL at the empty string → Task 9 URL test fails.

Record the test node id that went red and its assertion message for each. A
collection error rather than an assertion failure does not count.

### V3 — Negative control (runs last)

After every mutation is reverted:

```bash
./run.sh uv run pytest
./run.sh uv run ty check src/
./run.sh uv run ty check .
```

Record pytest's summary line verbatim and both ty exit statuses. Run this after
V2 so a green result is not merely the absence of exercise.

### V4 — ty scope guard (regression check on the previous plan)

The previous round narrowly scoped an `unresolved-import` suppression to
`tests/conftest.py:27`. Confirm that is still narrow: create
`src/wherewolf/_ty_probe.py` containing
`from definitely_not_a_real_module import something`, run
`./run.sh uv run ty check src/`, confirm it **fails** and record the diagnostic,
then delete the probe and confirm `git status --short src/` is empty. A passing
ty here means someone re-broadened the suppression.

### V5 — Manual GUI verification (DEFERRED, not performed by the implementer)

Requires a live display. State as deferred; do not claim as done.

- `Ctrl+Q` actually quits under a real window manager.
- The export modal is genuinely modal and focus returns correctly on cancel.
- Row striping is visible against the user's active desktop palette.
- Columns can be dragged by mouse in catalog, schema, and history.
- The editor's horizontal scrollbar appears only when a line overflows.
- Each Help dialect link opens the right page in a real browser.

### Explicitly not verified

- No application-wide Qt palette is introduced, so nothing here changes how the
  window looks outside the SQL editor.
- No screenshot renderer is added; the dark README image remains unreproducible
  from the repo.
- Spark-engine paths remain excluded by the `not spark` pytest marker.
- Task 4 lowers `profile_max_bytes` rather than using a genuinely large file, so
  real large-file profiling performance is untested.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished desktop-ui-refinements
```

This writes:

```text
/tmp/wherewolf/desktop-ui-refinements_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer desktop-ui-refinements`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/desktop-ui-refinements-review-*.md
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
   scripts/orchestration/clear-finished desktop-ui-refinements
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
   git add docs/review/desktop-ui-refinements-review-*.md
   git commit -m "docs(review): record desktop-ui-refinements review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished desktop-ui-refinements
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer desktop-ui-refinements` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed desktop-ui-refinements
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize desktop-ui-refinements
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/desktop-ui-refinements_finalized
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
scripts/orchestration/finalize desktop-ui-refinements
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/desktop-ui-refinements_finished
/tmp/wherewolf/desktop-ui-refinements_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
