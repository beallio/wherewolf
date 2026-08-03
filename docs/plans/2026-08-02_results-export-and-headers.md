# Plan: Default query, export controls and header type badges (results-export-and-headers)

## Context

Three defects reported against build `f3fa202`. Each was located in the code before this
plan was written; every file:line below is verified.

### D1 — the starter query hardcodes `LIMIT 10`, and the preview default is too small

`main_window.py:576` fills the editor after the first dataset is added:

```python
self.editor.setText(f"SELECT * FROM {quote_identifier(first.alias)} LIMIT 10")
```

The preview limit already bounds what is fetched, so the literal `LIMIT 10` is redundant —
and worse, it silently caps the result at ten rows even when the user raises the preview
limit, because the SQL clause wins.

The preview default is `100`:

- `services/settings_service.py:24` — `DEFAULT_PREVIEW_LIMIT: Final = 100`
- `services/execution_request_builder.py:28` — `preview_limit: int = 100`

Both must become `1000`. The preview spinbox range is already `(10, 1000)`, so `1000` is a
valid value and no range change is needed.

### D2 — duplicate export buttons, and the file dialog offers every format

**Duplicate controls.** `main_window.py:752-762` adds three `QToolButton`s to the results
export row — `export_preview_button`, `export_full_button`, `export_selection_button` —
alongside the controls that already cover the same ground:

- `export_scope_selector` (`main_window.py:733-737`) with `Preview` / `Full results` / `Selection`
- `export_format_selector` (`main_window.py:719`)
- `export_button` (`main_window.py:746`), which dispatches on the scope selector via
  `_export_selected_scope` (`main_window.py:499-506`)

So scope is selectable twice, and the buttons crowd the row. The three `QToolButton`s are
redundant. The same actions remain in the Query menu, which is where their keyboard
shortcuts live — those must not be removed.

**The dialog ignores the chosen format.** `services/export_destination.py:30-31`:

```python
def export_file_filter() -> str:
    return "Export files (" + " ".join(f"*.{fmt.value}" for fmt in ExportFormat) + ")"
```

Every format is offered regardless of what the user selected, so choosing Parquet still
presents CSV and XLSX in the save dialog.

### D3 — header type indicators are not legible

`widgets/result_table_view.py:55-86` draws an 18x18 pixmap, fills a shape with the
palette's `Highlight` colour, and centres a one-character glyph (`#`, `T`, `D`, `✓`) in a
16x16 rect using `HighlightedText`. At that size the glyph is mush, `Highlight` is a
selection colour rather than a content colour, and the pixmap is not rendered for HiDPI.

**Maintainer decision: replace the icons with short uppercase text badges** — `INT`,
`TXT`, `DATE`, `BOOL` — rendered as real text at the real font size. Legible at any DPI and
self-explanatory without learning a symbol set, at the cost of slightly wider headers.

### D4 — the Preferences font size does not change the editor font

The wiring looks correct — `main_window.py:985` calls `self.editor.set_font_size(...)`,
which reaches `_apply_font_size` (`widgets/sql_editor.py:257`) — but the text does not
resize. Measured on a running window:

```text
before                       widget.font()=12  lexer.defaultFont(0)=12  lexer.font(0)=9
                             lexer.font(keyword 5)=9   lexer.font(identifier 11)=9
after set_font_size(28)      widget.font()=28  lexer.defaultFont(0)=28  lexer.font(0)=9
                             lexer.font(keyword 5)=9   lexer.font(identifier 11)=9
```

**QScintilla renders from the lexer's per-style fonts**, and those stay at 9pt.
`_apply_font_size` sets the widget font and `lexer.setDefaultFont(...)`, but
`setDefaultFont` only affects styles that have not been given an explicit font — and the
theme work assigned per-style attributes, so every style ignores it. The setting is saved
and restored correctly; only the rendering never changes.

**Slug used throughout this plan:** `results-export-and-headers`

---

## Orchestration Contract

**Slug:** `results-export-and-headers`

**Plan file:**

```text
docs/plans/2026-08-02_results-export-and-headers.md
```

**Implementation branch:**

```text
feat/results-export-and-headers
```

**Round-complete marker:**

```text
/tmp/wherewolf/results-export-and-headers_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/results-export-and-headers_finalized
```

**Review notes:**

```text
docs/review/results-export-and-headers-review-*.md
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
git checkout -b feat/results-export-and-headers
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_results-export-and-headers.md
git commit -m "docs(plan): add results-export-and-headers implementation plan"
```

---

## Implementation Tasks

Work the tasks in order. **One commit per task**, Conventional Commits, TDD: write the
failing test, watch it fail, then implement.

Tests must reach each behaviour from `MainWindow` the way a user would, and must assert
`isVisible()` where visibility is the point — this repo has shipped controls that existed
but were hidden, and a `findChild` that returns a hidden widget passes a naive check.

### Task 1 — starter query without `LIMIT`, preview default 1000 (D1)

Drop the `LIMIT 10` clause from the auto-filled query at `main_window.py:576` so it reads
`SELECT * FROM <alias>`. Change `DEFAULT_PREVIEW_LIMIT` (`settings_service.py:24`) and the
`preview_limit` parameter default (`execution_request_builder.py:28`) from `100` to `1000`.

Do not change the spinbox range; `1000` is already its maximum.

Tests: the auto-filled text contains no `LIMIT`; a fresh `SettingsService` returns `1000`;
an `ExecutionRequest` built without an explicit limit carries `preview_limit == 1000`. Also
assert the auto-fill still does not overwrite text the user has already typed — that guard
exists and must not regress.

### Task 2 — remove the duplicate export buttons (D2)

Delete the three `QToolButton`s created at `main_window.py:752-762` and the loop that
builds them. Keep `export_scope_selector`, `export_format_selector`, `export_button`, and
every Query-menu action.

Tests: no widget named `export_preview_button`, `export_full_button` or
`export_selection_button` exists; `export_button`, `export_scope_selector` and
`export_format_selector` are all present **and visible** with the window shown at 1024px;
the Query menu still exposes the three export actions. Assert on the menu too — removing a
button must not remove the only route to the behaviour.

### Task 3 — the save dialog offers only the selected format (D2)

Make the export file filter depend on the chosen `ExportFormat` instead of listing all of
them. `export_file_filter()` (`export_destination.py:30`) currently takes no argument and
has callers — update it and its call sites together rather than leaving a second function
behind.

Tests: with Parquet selected, the filter string passed to the file dialog names Parquet and
does **not** contain `csv` or `xlsx`; repeat for CSV and XLSX. Capture the arguments handed
to `QFileDialog.getSaveFileName` rather than asserting on the function's return value — the
defect is in what the user is shown.

Then assert end-to-end that exporting with Parquet selected still writes a readable Parquet
file, so narrowing the filter has not broken the write path.

### Task 4 — header type badges (D3)

Replace the pixmap icons with short uppercase text badges in the result header: `INT` for
integers, `FLOAT` for floats (or `NUM` if you prefer one numeric badge — state which you
chose and why), `TXT` for strings, `DATE` for temporal types, `BOOL` for booleans, and a
sensible fallback for anything else. Render as text, not as a generated pixmap.

Remove `_build_dtype_icon` and the `DecorationRole` wiring it fed if nothing else uses
them; leaving them behind recreates this repo's dead-code pattern. Keep `_dtype_family` if
the badge mapping still needs it.

The full dtype must remain available in the header tooltip, as it is today
(`'age: Int64'`, `'when: Date'`).

Tests: a frame with integer, string, date and boolean columns yields four **distinct**
badge strings; the badge text is retrievable from the header via the model's
`DisplayRole` (or whichever role you use) alongside the column name; the tooltip still
names the actual dtype. Assert the badges differ from each other — four identical badges
would pass a naive "badge is non-empty" check, which is exactly how the previous icon test
failed to catch a real defect.

### Task 5 — make the Preferences font size actually resize the editor (D4)

Apply the chosen size to the lexer's **per-style** fonts, not only to the widget font and
`setDefaultFont`. `QsciLexer.setFont(font)` applies to every style; per-style
`setFont(font, style)` also works if you need to preserve differences. Keep the existing
save/restore behaviour, which is already correct.

Tests: after `set_font_size(28)`, assert `lexer.font(style).pointSize() == 28` for the
default, keyword and identifier styles — the three measured above as stuck at 9 — and that
`font_size` and the persisted setting also report 28. Asserting on `defaultFont` alone is
not sufficient: it already reports the new size today while the editor renders unchanged,
so a test against it passes on the unfixed code.

Also assert the size survives a settings round-trip through a new `SqlEditor`.

### Cross-cutting requirements

- Do not weaken, skip or delete existing tests.
- Do not remove the Query-menu export actions or their shortcuts.
- Do not remove `timid = true`, the `pyarrow` import in `execution/registry.py`, or the
  overwrite confirmation in `file_dialog_service.py`.
- Do not change `EngineKind` or the sqlglot identifiers in `DIALECT_MAPPING`.
- Do not reintroduce a `QScrollArea` in the toolbar, or an update-check control.
- Do not bump the version, tag, or touch `main`.
- Run `./run.sh uv run ty check .` over the whole repo before committing — a `src/`-only
  check passes while the pre-commit hook fails on `tests/`.

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

Run the gates and record the actual output, not a conclusion:

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check .
./run.sh uv run pytest
```

Record in the session log:

1. The auto-filled editor text after adding a dataset, and the same after adding one while
   the editor already contains user text.
2. `SettingsService(...).restore_preview_limit()` on a fresh profile, and
   `ExecutionRequest.preview_limit` for a request built without an explicit limit.
3. The full list of object names in the results export row, showing the three removed
   buttons are absent and the retained controls are present with `isVisible() is True` at a
   1024px window width.
4. The Query menu's action texts.
5. The exact filter string handed to `QFileDialog.getSaveFileName` for each of CSV, Parquet
   and XLSX.
6. The row count and first rows of a Parquet file written through the Export button.
7. The four header badges for an int/str/date/bool frame and their tooltips.
8. `lexer.font(style).pointSize()` for the default, keyword and identifier styles before and
   after applying a new Preferences font size, alongside `widget.font().pointSize()`.

### Negative controls

Mandatory for tasks 1, 2, 3 and 4, and each must run against the **full** suite
(`./run.sh uv run pytest`), not a single test file:

- restore `LIMIT 10` in the auto-filled query → task 1's test must fail;
- re-add one of the three export `QToolButton`s → task 2's test must fail;
- make `export_file_filter` list every format again → task 3's test must fail;
- make every dtype map to the same badge string → task 4's test must fail;
- revert Task 5 to setting only `setDefaultFont` → task 5's test must fail. This one matters
  most: the pre-fix code already passes a `defaultFont`-based assertion, so a guard aimed at
  the wrong property would look green against the very bug being fixed.

For each, record the failing test name and the pass/fail tallies before and after.

**Before trusting any negative control, prove the mutation actually changed the file** —
print the mutated line, or diff it. A mutation that fails to apply produces the same green
suite as a guard that does not bite, and this project has repeatedly been misled by exactly
that. Likewise, a mutation that fails twenty tests proves coupling rather than coverage;
prefer a mutation that fails only the guard in question.

These steps follow `references/verification-standards.md`; do not restate it.

## Deferred

Visual weight of the text badges in narrow columns, and header layout once badges widen the
columns, are manual maintainer checks — record them in
`docs/review/manual-acceptance-checklist.md` rather than claiming them verified.

Font rendering at very large sizes, and how the editor's margin width tracks a resized
font, are manual maintainer checks.

Raising the preview default to 1000 is **not** benchmarked here: no measurement is taken of
render time or memory for a 1000-row preview on a wide frame. State that explicitly rather
than implying the new default was performance-tested.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished results-export-and-headers
```

This writes:

```text
/tmp/wherewolf/results-export-and-headers_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer results-export-and-headers`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/results-export-and-headers-review-*.md
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
   scripts/orchestration/clear-finished results-export-and-headers
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
   git add docs/review/results-export-and-headers-review-*.md
   git commit -m "docs(review): record results-export-and-headers review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished results-export-and-headers
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer results-export-and-headers` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed results-export-and-headers
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize results-export-and-headers
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/results-export-and-headers_finalized
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
scripts/orchestration/finalize results-export-and-headers
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/results-export-and-headers_finished
/tmp/wherewolf/results-export-and-headers_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
