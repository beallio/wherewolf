# Plan: Desktop feature parity and UI defects (desktop-parity)

## Context

The Streamlit->PyQt6 migration shipped a release candidate, but the maintainer ran the
installed app and found it is **not at feature parity** with the Streamlit version. Two
fully-built widgets are dead code, the Edit menu is empty, and editor text is invisible.

Streamlit was deleted in commit `9212309`. Read the pre-cutover files with
`git show 9212309^:src/wherewolf/app.py` (and `ui/results.py`, `ui/file_browser.py`)
to see the behaviour being restored. Do this before writing code — the goal is parity
with what actually existed, not an invention.

**A related crash is already fixed on `dev` (commit `6f0c272`) — do not revisit it.**
`src/wherewolf/execution/registry.py` imports `pyarrow` at module scope and the comment
there says it is load-bearing. Leave that import alone.

### Defects to close

**D2 — TranslationPanel is dead code.** `desktop/widgets/translation_panel.py` and
`services/translation_view_model.py` are fully implemented and unit-tested, but nothing
imports them. `main_window.py` builds only Results and Messages tabs. Streamlit showed
SQL transpiled to a user-chosen target dialect (`9212309^:src/wherewolf/ui/results.py:42-71`).
`sqlglot.transpile` is live at `translation/translator.py:33`.

**D3 — SchemaPanel is dead code.** `desktop/widgets/schema_panel.py` renders columns and
types but `MainWindow` never constructs it. `models/catalog_model.py` exposes only a
"Schema status" column, so the catalog dock shows Alias/File/Format and nothing more.
Streamlit rendered per-alias columns and types (`9212309^:src/wherewolf/app.py:263-303`).

**D4 — Edit menu is empty.** `main_window.py:449-450` creates the menu and adds zero
actions. The editor already owns `_undo_action`, `_redo_action`, `_cut_action`,
`_copy_action`, `_paste_action`, `_toggle_comment_action` (`sql_editor.py:129-150`) for
its context menu; the menubar simply never receives them.

**D5 — Editor text is invisible.** `sql_editor.py:116` hardcodes
`setCaretLineBackgroundColor(QColor("#f5f5f5"))` — near-white — while the editor paper
follows the desktop's dark palette and `QsciLexerSQL` is never given explicit colours.
Styles with no explicit colour (default, identifier, operator) render light-on-light. The
maintainer's screenshot shows `SELECT * FROM t LIMIT 10` displaying as
`SELECT   FROM        LIMIT 10` — only keywords and the numeric literal were visible.

**D6 — remaining parity gaps**, all verified against the pre-cutover tree:

| gap | Streamlit source | current desktop state |
|---|---|---|
| input-dialect selector + transpile before run | `app.py:371-413` | absent; `main_window.py:195` hardcodes duckdb/spark |
| export-format chooser (CSV/Excel/Parquet) | `ui/results.py:88-108` | absent; `main_window.py:273` always CSV |
| preview-size control (10-1000, default 100) | `app.py:310` | absent; fixed at 1000 in `execution_request_builder.py:21` |
| editor-theme selector | `app.py:332-363` | absent; only font size persists |
| auto-fill `SELECT * FROM <alias> LIMIT 10` after first dataset | `app.py:229-235` | absent |

**Slug used throughout this plan:** `desktop-parity`

---

## Orchestration Contract

**Slug:** `desktop-parity`

**Plan file:**

```text
docs/plans/2026-08-02_desktop-parity.md
```

**Implementation branch:**

```text
feat/desktop-parity
```

**Round-complete marker:**

```text
/tmp/wherewolf/desktop-parity_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/desktop-parity_finalized
```

**Review notes:**

```text
docs/review/desktop-parity-review-*.md
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
git checkout -b feat/desktop-parity
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_desktop-parity.md
git commit -m "docs(plan): add desktop-parity implementation plan"
```

---

## Implementation Tasks

Work in this order. **One commit per task**, Conventional Commits, each with its tests
passing before you move on. Every task is TDD: write the failing test first, watch it
fail, then implement.

### Why the existing tests did not catch any of this

`tests/test_translation_panel.py` and `tests/test_schema_panel.py` pass today — they
construct the widgets in isolation. `tests/test_main_window.py` asserts the Edit menu
*object* exists. Every one of these defects shipped past a green suite. **So for each
task, the test must assert the thing is reachable by a user from `MainWindow`, not that
a class can be instantiated.** A test that would still pass with the feature unreachable
is not an acceptable test for this plan.

### Task 1 — Edit menu (D4)

Write a test asserting `main_window.edit_menu.actions()` is non-empty and contains
actions whose text covers undo, redo, cut, copy, paste and toggle-comment. Then populate
the menu in `_build_menus`, reusing the actions the editor already owns rather than
creating duplicates that would drift. Add separators between the undo/redo, clipboard,
and comment groups. Confirm the standard shortcuts still work through the menubar.

### Task 2 — editor colours (D5)

Write a test that computes the actual rendered contrast: for the caret-line background
and for each of the lexer styles that carry user text (default, identifier, operator,
plus keyword/number/string), assert the foreground and the caret-line background are not
near-identical in luminance. Assert against computed luminance, **not** colour literals —
a literal-matching test would pass again the moment someone changes the palette.

Then give `QsciLexerSQL` an explicit, self-consistent colour scheme rather than letting
unstyled tokens inherit the system palette, and derive the caret-line background from the
editor's actual paper colour instead of the hardcoded `#f5f5f5`.

### Task 3 — schema panel (D3)

Write a test that gets from `MainWindow` to visible schema content: add a dataset, let
the schema worker finish, and assert the panel shows the column names and types for that
alias. Then construct `SchemaPanel` in `MainWindow`, place it where a user will find it
(a dock or a tab beside the catalog), and connect it to the existing schema results the
`SchemaWorker` already produces. Do not rewrite `schema_panel.py` — it works; it is
unreached.

### Task 4 — translation panel (D2)

Write a test that selects a target dialect from `MainWindow` and asserts the panel
displays the transpiled SQL for the current editor text. Then add the panel as a third
results tab beside Results and Messages, wired to the existing `TranslationViewModel`.
Include a target-dialect selector; use the dialect list `sqlglot` actually supports
rather than a hand-maintained copy.

### Task 5 — input dialect + transpile before execution (D6)

Streamlit let the user pick the *source* dialect (including Azure SQL / tsql) and
transpiled to the engine dialect before running. Add that control and thread it through
`ExecutionRequest.source_dialect`, which already exists. Test that choosing a non-native
source dialect changes the `executable_sql` that reaches the engine — not merely that a
combobox exists.

### Task 6 — export-format chooser (D6)

`main_window.py:273` always requests `ExportFormat.CSV`. Let the user choose CSV, Excel
or Parquet; all three already exist in the export layer. Test that choosing Parquet
produces a Parquet file on disk with readable contents, and likewise for Excel — assert
on the artifact, not on the call arguments.

### Task 7 — preview size + editor theme (D6)

Add a preview-row-count control (10-1000, Streamlit's default was 100; the desktop
currently hardcodes 1000 in `services/execution_request_builder.py:21`) and an editor
theme selector, both persisted through the existing `SettingsService`. Test that the
chosen preview size reaches `ExecutionRequest.preview_limit` and that the setting
survives a settings round-trip.

### Task 8 — auto-fill starter query (D6)

After the first dataset is added and no user text is present, fill the editor with
`SELECT * FROM <alias> LIMIT 10`, quoting the alias with the existing
`services/identifier_quoting.py`. Must not overwrite text the user has already typed —
test that case explicitly.

### Cross-cutting requirements

- Do not weaken, skip or delete any existing test to make these pass.
- Do not remove `timid = true` from `[tool.coverage.run]`; it prevents a Qt tracer crash.
- Do not remove the `pyarrow` import in `src/wherewolf/execution/registry.py`.
- Do not bump the version, tag, or touch `main`. Those are maintainer gates.
- Every new user-facing control must be reachable from `MainWindow` without private
  attribute access in the test.

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

Automated, and required before marking the round complete:

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
./run.sh uv run pytest
```

Then prove each defect is actually closed, and record the output in your session log:

1. Edit menu has actions — print `len(edit_menu.actions())` and the action texts.
2. Editor contrast — print the computed luminance pairs the test asserts on.
3. Schema panel — print the column names the panel exposes after a real dataset add.
4. Translation panel — print the transpiled SQL for one non-trivial statement.
5. Source dialect — print `executable_sql` for a tsql input against the duckdb engine,
   showing it differs from the original.
6. Export — list the produced `.parquet` and `.xlsx` files and their row counts.
7. Preview size — print the `preview_limit` that reached `ExecutionRequest`.
8. Auto-fill — print the editor text after adding a dataset, and after adding one when
   the editor is already non-empty.

**Negative controls.** For at least tasks 1, 2 and 8, mutate the implementation to
reintroduce the defect and confirm the new test fails. Paste the failing output into
your session log. A test you have not seen fail is not evidence.

## Deferred verification

Appearance of the new colour scheme, native dialog behaviour, and the feel of the schema
and translation panels are **manual maintainer checks** — automated tests can prove the
content is present and legible by luminance, not that it looks good. Note them in
`docs/review/manual-acceptance-checklist.md` rather than claiming them verified.

macOS and Windows remain covered only by the offscreen `qt-smoke` CI job.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished desktop-parity
```

This writes:

```text
/tmp/wherewolf/desktop-parity_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer desktop-parity`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/desktop-parity-review-*.md
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
   scripts/orchestration/clear-finished desktop-parity
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
   git add docs/review/desktop-parity-review-*.md
   git commit -m "docs(review): record desktop-parity review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished desktop-parity
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer desktop-parity` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed desktop-parity
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize desktop-parity
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/desktop-parity_finalized
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
scripts/orchestration/finalize desktop-parity
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/desktop-parity_finished
/tmp/wherewolf/desktop-parity_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
