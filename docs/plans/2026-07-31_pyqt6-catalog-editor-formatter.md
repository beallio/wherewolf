# Plan: PyQt6 Desktop Migration - Catalog, Editor, Formatter (Phases 4-6) (pyqt6-catalog-editor-formatter)

## Context

This is the **second** slice of the PyQt6/QScintilla desktop migration. The full design
lives in `docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md` (the "migration
document"). Read its Sections 10-12 and Phases 4-6 of Section 20 before starting.

**This plan implements Phases 4, 5 and 6 only:** the dataset catalog with native file
dialogs and drag/drop, the QScintilla SQL editor foundation, and the Format SQL action.

**Phase 7 (schema-aware IntelliSense) is explicitly NOT in this plan** and gets its own.
Do not build a completion service, a completion popup adapter, or call tips here. The
migration document groups 4-7 as one PR; we are deliberately splitting after Phase 6
because completion is the hardest single piece in the migration and needs its own review
cycle.

Also out of scope: query execution (Phase 8), the result grid (Phase 9), schema/translation
panels (Phase 10), history and export (Phases 11-12), Spark changes (Phase 13), and any
Streamlit removal (Phase 14).

### What already exists — build on it, do not rebuild it

The previous slice (`docs/plans/2026-07-31_pyqt6-desktop-foundation.md`, merged to `dev`
as `f98e2c4`) already delivered:

- `src/wherewolf/domain/models.py` — frozen, slotted `ColumnSchema`, `CatalogEntry`,
  `CatalogBinding`, `ExecutionRequest`, `QueryResult`, `SchemaResult`, `SqlDiagnostic`.
  **`CatalogEntry` and `CatalogBinding` already exist — use them, do not define new ones.**
  `QueryResult` enforces its success/failure invariant in `__post_init__`; keep that style.
- `src/wherewolf/domain/enums.py` — `EngineKind`, `SourceFormat`, `ExecutionStatus`,
  `CompletionKind`. **`SourceFormat.from_path()` already exists**, already resolves
  case-insensitively, already has no `.xls` member, and already raises
  `UnsupportedFormatError` for unsupported suffixes. Reuse it for all format detection.
- `src/wherewolf/domain/errors.py` — `WherewolfError`, `UnsupportedFormatError`,
  `EngineUnavailableError`, `TranslationError`. Add new error types here, not elsewhere.
- `src/wherewolf/execution/registry.py` and `base.py` — the engine registry and protocols.
  You need the registry only to *read schema*; do not change its execution behavior.
- `src/wherewolf/services/settings_service.py` — `SettingsService` over `QSettings` with
  versioned keys and **scoped** corrupt-value fallback. It currently persists window
  geometry, window state, splitter sizes and editor font size. Extend it; do not replace it.
- `src/wherewolf/desktop/actions.py` — `build_actions()` returns a frozen `DesktopActions`
  bundle. `run` and `cancel` are wired; **`add_datasets` and `format_sql` currently exist
  but are `setEnabled(False)` with the tooltip "Unavailable in Phase 3 desktop foundation".
  This plan enables both and removes those tooltips.**
- `src/wherewolf/desktop/main_window.py` — `QMainWindow` with a toolbar, a left
  "Dataset Catalog" `QDockWidget` (currently a placeholder), a vertical `QSplitter`
  central area, a bottom `QTabWidget`, a status bar, and File/Edit/Query/View/Help menus.
  `_build_catalog_dock()` and `_build_central_area()` are the seams you extend.
- `src/wherewolf/translation/translator.py` — `translate()` (legacy, Streamlit-only) and
  `translate_statements()` (statement-preserving). **Formatting is NOT translation** —
  see Task 11.

### Hard constraint: Streamlit must keep working, unchanged

Same as the previous slice, and it held perfectly there:

- `src/wherewolf/app.py`, `src/wherewolf/engines.py`, `src/wherewolf/ui/*`,
  `src/wherewolf/export/*`, `src/wherewolf/storage/*`, `src/wherewolf/constants.py` and
  `.streamlit/` are **not modified by this plan**.
- `[project.scripts] wherewolf` keeps pointing at `wherewolf.cli:main`.
- Every currently-passing test must still pass.

**Specifically on `.xls`:** migration-document Section 11.1 says to strip the false `.xls`
claim from constants, README, UI filters and tests. The desktop half is already satisfied —
`SourceFormat` has no `.xls` member, so the new catalog rejects it. But
`src/wherewolf/constants.py:4` still lists `.xls` in `SUPPORTED_EXTENSIONS`, and that
constant is consumed only by the Streamlit `file_browser.py` and pinned by
`tests/test_constants.py`. **Leave both alone.** Removing it is cutover-plan work; doing it
here would modify the Streamlit path for no desktop benefit.

### Repo mechanics that will fail your commits if ignored

- `.git/hooks/pre-commit` runs `ruff check .`, `ruff format .`, **`ty check .` over the
  whole repo including tests**, `pytest`, then `scripts/check_tdd.sh`.
- `scripts/check_tdd.sh` requires a **flat** `tests/test_<basename>.py` for every staged
  `src/**/*.py`. It does not understand subdirectories. `src/wherewolf/desktop/widgets/sql_editor.py`
  therefore requires `tests/test_sql_editor.py`. **Use flat test filenames.** Do not create
  the nested `tests/…` tree from migration-document Section 22.2 and do not edit
  `check_tdd.sh`.
- The pre-commit hook runs `git add -u`, which re-stages every modified **tracked** file.
  Untracked files are unaffected. Stage each commit's new files explicitly with
  `git add <path>`; where a clean split is impossible, use the fewest coherent commits and
  say so in the session log.
- **ruff is on the 0.16 default rule set** (`I`, `BLE`, `UP`, `SIM`, `RUF`, `DTZ`, `B`,
  `PIE`, …), which is much wider than pre-0.16. Any `except Exception` you add trips
  `BLE001`; if the broad catch is a deliberate boundary, annotate it `# noqa: BLE001` with
  a one-line site-specific reason, matching the convention in `src/wherewolf/execution/`.
  Never add a blanket ignore.
- All commands go through `./run.sh` so caches stay under `/tmp/wherewolf`.
  `/tmp/wherewolf` is a symlink to `~/.local/state/wherewolf-cache` because `/tmp` is a
  quota-limited tmpfs; the `AGENTS.md` Section 5 paths are unchanged.
- Qt tests run headless. `tests/conftest.py` already sets `QT_QPA_PLATFORM=offscreen`
  before any Qt import — do not duplicate that.

### Baseline

`dev` at `672111e` is fully green:

```text
107 passed, 1 skipped
```

with `ruff check`, `ruff format --check` and `ty check src/` all clean, verified on
Python 3.12 and 3.14. **Any failure in your baseline run is a real problem — investigate
before writing code.**

**Slug used throughout this plan:** `pyqt6-catalog-editor-formatter`

---

## Orchestration Contract

**Slug:** `pyqt6-catalog-editor-formatter`

**Plan file:**

```text
docs/plans/2026-07-31_pyqt6-catalog-editor-formatter.md
```

**Implementation branch:**

```text
feat/pyqt6-catalog-editor-formatter
```

**Round-complete marker:**

```text
/tmp/wherewolf/pyqt6-catalog-editor-formatter_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/pyqt6-catalog-editor-formatter_finalized
```

**Review notes:**

```text
docs/review/pyqt6-catalog-editor-formatter-review-*.md
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
# ORCH_LOCAL_ONLY: local trial branch, skipping origin pull
git checkout -b feat/pyqt6-catalog-editor-formatter
```

Commit this plan first:

```bash
git add docs/plans/2026-07-31_pyqt6-catalog-editor-formatter.md
git commit -m "docs(plan): add pyqt6-catalog-editor-formatter implementation plan"
```

---

## Implementation Tasks

Work in order. Write the failing test first, watch it fail, then implement. Run
`./run.sh uv run pytest` after every task, not just at the end.

Record real command output in the session log. Never write "passed" — write the tally the
tool printed. **Create the session log in Task 1 and commit it in Task 1**; the previous
slice lost a whole round to leaving it until the end.

---

### Task 1 — Baseline and session log

1. Emit the `AGENT_PROTOCOL_HANDSHAKE` from `AGENTS.md` Section 1 after actually running
   `pwd`, `ls`, `git status` and inspecting `pyproject.toml` / `uv.lock` / `run.sh` /
   `.protocol`.
2. Create **and commit** `docs/agent_conversations/2026-07-31_pyqt6-catalog-editor-formatter.md`
   with the `AGENTS.md` Section 14 headings: date, task objective, files modified, tests
   added, design decisions, results. Append to it as you go and commit updates with each
   task rather than saving it for the end.
3. Capture the baseline:

   ```bash
   set -o pipefail
   ./run.sh uv sync --all-extras --dev
   ./run.sh uv run pytest 2>&1 | tail -20
   ```

   Expected: `107 passed, 1 skipped`. Record the summary line and `git rev-parse HEAD`.

Commit: `docs: record catalog-editor-formatter baseline`.

---

### Task 2 — `FileDialogService` (Phase 4)

**Red.** `tests/test_file_dialog_service.py`:

- the protocol is satisfied by a fake that returns a fixed tuple of paths;
- `choose_dataset_files` returning an empty tuple represents cancellation;
- the production adapter builds the exact filter string from migration-document
  Section 11.1, containing `*.csv *.parquet *.json *.jsonl *.xlsx` and **not** `.xls`;
- the filter list is derived from `SourceFormat`, so adding a format cannot silently
  desynchronise the dialog filters from what the catalog accepts. Assert this by checking
  every `SourceFormat` member's extension appears in the generated filter string.

**Green.** `src/wherewolf/desktop/dialogs/__init__.py` and
`src/wherewolf/desktop/dialogs/file_dialog_service.py` with a `FileDialogService`
`Protocol`, a `QtFileDialogService` production adapter calling
`QFileDialog.getOpenFileNames()`, and a `FakeFileDialogService` for tests.

**No automated test may open a native dialog.** The fake is injected everywhere.

`check_tdd.sh` needs `tests/test_file_dialog_service.py` — the name already matches.

Commit: `feat(desktop): add injectable native file dialog service`.

---

### Task 3 — `CatalogService` (Phase 4)

**Red.** `tests/test_catalog_service.py`. This is pure logic with no Qt — test it hard:

- `add_paths` resolves paths **before** the duplicate check, so `./data/a.csv` and an
  absolute path to the same file collapse to one entry (build the case with `tmp_path`
  and a symlink);
- adding the same resolved path twice yields one entry and reports the duplicate;
- alias generation from filenames sanitises to a valid SQL identifier;
- collisions get deterministic suffixes: `orders`, `orders_2`, `orders_3`;
- uniqueness is **case-insensitive** via `casefold()` — adding `Orders.csv` when `orders`
  exists produces `orders_2`, not a second `orders`;
- an unsupported extension is reported, not silently dropped, and does not abort the
  other paths in the same call;
- `rename` rejects empty/invalid aliases with an actionable message and rejects a rename
  that collides case-insensitively with an existing alias;
- `remove` by `entry_id`;
- `update_schema(SchemaResult)` attaches columns on success and attaches
  `schema_error` on failure — a failure must **not** be stored as an empty column tuple;
- `snapshot()` returns `CatalogBinding` values that do **not** change when the service is
  subsequently mutated (add an entry after taking the snapshot and assert the snapshot is
  unchanged).

**Green.** `src/wherewolf/services/catalog_service.py`. Use the existing `CatalogEntry`,
`CatalogBinding`, `SchemaResult` and `SourceFormat.from_path`. No Qt imports in this file.

Commit: `feat(services): add UI-neutral dataset catalog service`.

---

### Task 4 — `CatalogModel` and the catalog dock (Phase 4)

**Red.** `tests/test_catalog_model.py` and `tests/test_catalog_dock.py`, using `qtbot`:

- model row/column counts track the service;
- columns are Alias, File, Format, Schema status (migration-document Section 11.3);
- the full path is exposed via `ToolTipRole`, not forced into a wide column;
- schema status renders distinctly for Loading, Ready and Error;
- an entry with `schema_error` shows the **real error text**, never "no columns detected";
- the model is updated only on the GUI thread — assert the model emits
  `dataChanged`/`modelReset` when the service changes, and never mutates from a worker;
- the dock hosts the view and is the same `QDockWidget` the main window already creates
  (do not add a second catalog dock).

**Green.** `src/wherewolf/desktop/models/__init__.py`,
`src/wherewolf/desktop/models/catalog_model.py` (a `QAbstractTableModel`), and
`src/wherewolf/desktop/widgets/__init__.py`,
`src/wherewolf/desktop/widgets/catalog_dock.py`. Replace the placeholder inside the
existing `MainWindow._build_catalog_dock()`.

Do not use `QTableWidget` and do not create a widget per cell.

Commit: `feat(desktop): add dataset catalog model and dock`.

---

### Task 5 — Add Datasets action and last-directory persistence (Phase 4)

**Red.** Extend `tests/test_actions.py` and `tests/test_settings_service.py`:

- `add_datasets` is **enabled** and its "Unavailable in Phase 3 desktop foundation"
  tooltip is gone;
- it carries `QKeySequence.StandardKey.Open` (`Ctrl+O` / `Cmd+O`);
- triggering it with the fake dialog service adds the returned paths to the catalog;
- a cancelled dialog (empty tuple) is a no-op — the catalog is unchanged and no error is
  shown;
- the dialog opens at the persisted last-dataset directory, and a successful add updates
  it;
- an unset last directory falls back to a sane default rather than raising;
- a corrupt stored last directory falls back **scoped**, leaving other settings intact —
  match the existing `SettingsService` pattern.

**Green.** Add last-dataset-directory to `SettingsService` using its existing versioned-key
and scoped-fallback style. Wire the action in `MainWindow` through the injected
`FileDialogService`.

Commit: `feat(desktop): wire native Add Datasets action`.

---

### Task 6 — Drag and drop (Phase 4)

**Red.** `tests/test_catalog_dock.py` additions. Construct `QDropEvent`/`QMimeData` with
`file://` URLs directly — do **not** drive the OS:

- multiple local files are accepted in one drop;
- directories are rejected (directory import is not implemented);
- unsupported extensions produce **one consolidated warning**, not one per file, and the
  supported files in the same drop are still added;
- paths already in the catalog are deduplicated by resolved path;
- a drop with no local files is ignored cleanly;
- drop and dialog go through the **same** `CatalogService.add_paths` call — assert this
  with a spy/mock so alias validation cannot drift between the two entry points.

**Green.** Accept `dragEnterEvent`/`dropEvent` on the catalog dock and the main window.
Put no alias logic in the widget.

Commit: `feat(desktop): accept dataset drag and drop`.

---

### Task 7 — Catalog context menu, inline rename, schema refresh (Phase 4)

**Red.** `tests/test_catalog_dock.py` additions:

- context menu offers Rename Alias, Remove, Refresh Schema, Copy Alias, Copy File Path,
  Insert Alias at Editor Cursor;
- rename via the model commits through `CatalogService.rename` and surfaces its error
  message on an invalid alias without corrupting the row;
- Copy Alias / Copy File Path put the expected text on `QApplication.clipboard()`;
- Remove deletes the right entry when several share a similar alias — assert by
  `entry_id`, never by display label;
- Refresh Schema re-runs inspection for an entry previously in the Error state.

**Green.** `src/wherewolf/desktop/widgets/catalog_dock.py`. Reuse the same `QAction`
objects where a command already exists.

Leave "Reveal in file manager" out; it is platform-specific and not required here.

Commit: `feat(desktop): add catalog context actions and inline rename`.

---

### Task 8 — Asynchronous schema loading (Phase 4)

Migration document Section 11.5: entries appear immediately, schema loads asynchronously.
Phase 10 owns the schema *panel*; this task only populates `CatalogEntry.schema`.

**Red.** `tests/test_schema_worker.py`:

- entries are added to the catalog **before** any schema work completes;
- a `SchemaResult` carrying columns moves the entry to Ready;
- a `SchemaResult` carrying an error moves it to Error **with the real message**;
- the worker never touches the Qt model directly — the GUI thread applies the result via
  a signal, asserted with `qtbot.waitSignal`;
- a result whose `entry_id` no longer exists (entry removed mid-flight) is discarded
  without raising;
- the GUI thread is not blocked while schema loads.

**Green.** `src/wherewolf/desktop/workers/__init__.py` and
`src/wherewolf/desktop/workers/schema_worker.py`. Read schema through the existing engine
registry. Emit domain objects, never widgets. Close request-scoped resources in `finally`.

Do not use sleep-based synchronisation; use `qtbot.waitSignal`.

Commit: `feat(desktop): load dataset schema off the GUI thread`.

---

### Task 9 — `StatementService`: quote- and comment-aware statement location (Phase 5)

This is pure logic and the correctness core of Run and Format. Build it before the editor.

**Red.** `tests/test_statement_service.py`:

- a document with one statement returns that statement;
- with several statements, the one containing the cursor is returned, for a cursor at the
  start, middle and end of each;
- **a semicolon inside a single-quoted string does not split a statement**;
- likewise inside a double-quoted identifier;
- likewise inside a `--` line comment;
- likewise inside a `/* */` block comment;
- an escaped quote inside a string does not terminate it;
- a trailing semicolon is reported so callers can preserve it;
- CRLF and LF documents both work and the reported offsets are correct for each;
- an empty or whitespace-only document returns no statement rather than raising;
- when no unambiguous statement can be identified the service says so explicitly — it must
  never silently discard statements (migration-document Section 12.2).

**Green.** `src/wherewolf/services/statement_service.py`. Return statement text plus its
start/end offsets. No Qt imports.

Commit: `feat(services): add quote-aware SQL statement locator`.

---

### Task 10 — `SqlEditor` on QScintilla (Phase 5)

**Red.** `tests/test_sql_editor.py` with `qtbot`:

- the widget constructs headless and round-trips text;
- a `QsciLexerSQL` (or a subclass) is assigned;
- the line-number margin is visible and widens for a 1000-line document;
- brace matching, caret-line highlight and auto-indent are configured;
- undo/redo, cut/copy/paste behave;
- find and replace, including replace-all, operate on the document;
- toggle-comment comments and uncomments a selection, and round-trips to the original;
- the font family/size come from `SettingsService` and a size change is persisted;
- **selection takes priority**: with text selected, the "text to run" is the selection;
  with no selection, it is the statement under the cursor, delegated to
  `StatementService` (assert the delegation with a spy — do not duplicate the parsing).

**Green.** `src/wherewolf/desktop/widgets/sql_editor.py` wrapping `QsciScintilla`, plus
the editor context menu (Undo/Redo, Cut/Copy/Paste, Toggle Comment). Place it in the
central splitter above the existing bottom `QTabWidget`.

Extend `QsciLexerSQL`'s keyword sets for DuckDB/Spark rather than writing a custom lexer.

**Do not add completion, call tips, or an autocompletion popup — that is Phase 7.**

Commit: `feat(editor): add QScintilla SQL editing foundation`.

---

### Task 11 — `SqlFormattingService` (Phase 6)

**Formatting is not translation.** It parses and regenerates in the **same** dialect. It
must never transpile to the engine dialect. Do not route it through
`Translator.translate_statements`.

**Red.** `tests/test_formatting_service.py`, covering migration-document Section 22.3:

- same-dialect parse and pretty-print;
- **multiple statements are all retained** — formatting a 3-statement document returns 3
  statements, in order;
- a trailing semicolon is preserved when present and not added when absent;
- the document's line-ending convention is preserved (CRLF stays CRLF);
- line comments and block comments survive, before and after expressions;
- quoted identifiers keep their quoting;
- a semicolon inside a string is not treated as a separator;
- DuckDB-specific and Spark-specific syntax each round-trip under their own dialect;
- **on parse failure the text is returned byte-for-byte unchanged** plus a
  `SqlDiagnostic` with a best-available line/column — assert byte equality, not "looks
  similar";
- the service never mutates its input.

**Green.** `src/wherewolf/services/formatting_service.py` returning a frozen
`FormattingResult(formatted_sql: str | None, diagnostics: tuple[SqlDiagnostic, ...])`.
Reuse the existing `SqlDiagnostic`. Use SQLGlot's parser and pretty-printer. No Qt imports.

Commit: `feat(services): add dialect-aware SQL formatting service`.

---

### Task 12 — Format SQL action (Phase 6)

**Red.** `tests/test_sql_editor.py` and `tests/test_actions.py` additions:

- `format_sql` is **enabled** and its "Unavailable in Phase 3" tooltip is gone;
- the toolbar action, the Query-menu action and the editor context-menu action are the
  **same `QAction` object** (`is`, not equality) — the previous slice established this
  convention for Run/Cancel;
- the shortcut is `Ctrl+Shift+F` on Windows/Linux and `Cmd+Shift+F` on macOS;
- with a selection, only the selection is reformatted and text outside it is untouched;
- with no selection, the current statement is reformatted;
- a single-statement document reformats wholly;
- **one Undo restores the exact pre-format document** — assert byte equality after a
  single `undo()`, which requires `beginUndoAction()`/`endUndoAction()` around the edit;
- cursor position, first visible line and horizontal scroll are restored within the bounds
  you document;
- on a parse error the document is byte-for-byte unchanged, an editor indicator is placed,
  and a diagnostic is reported.

**Green.** Wire the shared action. Apply the replacement inside one undo transaction.
Report diagnostics through a signal the Messages panel will consume in Phase 10 — do not
build that panel now.

Commit: `feat(editor): add dialect-aware SQL formatting action`.

---

### Task 13 — README and close out the session log

1. Update `README.md`: `wherewolf-desktop` now offers a dataset catalog with native
   file dialogs and drag/drop, a QScintilla SQL editor, and Format SQL. State plainly that
   **query execution is not yet implemented** in the desktop shell. Per `AGENTS.md`
   Section 13, bump the `cacheBuster` on README image/badge URLs (currently `12`) to `13`.
2. Finish the session log: files added/modified per task, tests added, the baseline and
   final pytest tallies, every deviation with its reason, and everything you could not
   verify.

Commit: `docs: document catalog editor and formatter workflow`.

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

Written to the standard in
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`: every
step can fail, and each says what failure looks like. Run in order — V4 deliberately
breaks things and V5 is the negative control that must run **after** the tree is restored.

Report output, not conclusions. "Record the tally", not "confirm the tests pass".

### V1 — Suite and gates

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"

output=$(./run.sh uv run pytest -q 2>&1)
printf '%s\n' "$output" | tail -5

failed=$(printf '%s\n' "$output" | awk '/^FAILED /{print $2}')
if [ -n "$failed" ]; then
  echo "FAIL: baseline is green, so any failure is a regression:"
  printf '%s\n' "$failed"
  exit 1
fi

passed=$(printf '%s\n' "$output" | grep -oE '[0-9]+ passed' | tail -1 | cut -d' ' -f1)
if [ -z "$passed" ] || [ "$passed" -le 107 ]; then
  echo "FAIL: passed count is '${passed:-<none>}', expected greater than 107"
  exit 1
fi
echo "OK: 0 failures; $passed passed (baseline 107)"
```

The standalone `output=$(...)` assignment propagates the pipeline's status (VS-06), and the
empty-string guard means a mangled summary cannot pass vacuously (VS-14).

Then `scripts/orchestration/run-quality-gates`, which **must exit 0**. All four gates are
clean on the baseline. **Failure looks like:** a non-zero exit from `ruff check`,
`ruff format`, `ty check src/` or `pytest`.

### V2 — Streamlit path provably untouched

```bash
git diff --name-only dev..HEAD -- \
  src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/storage/ src/wherewolf/constants.py .streamlit/
```

**Expected output: nothing.** Any filename means the hard constraint was broken — revert
that file. Then confirm the Streamlit suites still pass:

```bash
./run.sh uv run pytest -q --no-cov tests/test_app.py tests/test_app_flow.py \
  tests/test_app_cancel.py tests/test_engines.py tests/test_constants.py
```

### V3 — No native dialog is ever opened by the suite

```bash
grep -rn "getOpenFileNames\|getSaveFileName\|QFileDialog" tests/ || echo "OK: no direct QFileDialog use in tests"
```

**Failure looks like:** any hit outside an explicit "the fake is used instead" assertion.
A test that opens a real dialog will hang CI. Also confirm the whole suite completes
without hanging by checking V1's wall-clock time is in the normal range (tens of seconds).

### V4 — Mutation checks: prove the new tests bite

Each mutation must make a **named** test fail. If the suite stays green, that test is
decoration — rewrite it before marking the round complete. Revert fully between each with
`git checkout -- <file>` and confirm `git status --short` is clean.

**Commit your work before running these.** Every check ends in `git checkout --`, which
against an uncommitted tree destroys the round.

1. **Statement locator ignores quoting.** In `statement_service.py`, make the splitter
   treat every `;` as a separator regardless of string/comment state.
   → the quoted-semicolon and comment tests in `tests/test_statement_service.py` must FAIL.

2. **Formatter drops trailing statements.** In `formatting_service.py`, return only the
   first formatted statement.
   → the multi-statement retention test in `tests/test_formatting_service.py` must FAIL.

3. **Formatter is destructive on parse error.** On failure, return `""` instead of the
   original text.
   → the byte-for-byte unchanged test must FAIL.

4. **Alias uniqueness becomes case-sensitive.** In `catalog_service.py`, compare aliases
   without `casefold()`.
   → the `Orders.csv` vs `orders` test in `tests/test_catalog_service.py` must FAIL.

5. **Format SQL loses its single-undo guarantee.** Remove the
   `beginUndoAction()`/`endUndoAction()` pair.
   → the one-Undo byte-equality test in `tests/test_sql_editor.py` must FAIL.

6. **Format SQL action identity breaks.** Build a second `QAction` for the context menu
   instead of reusing the shared one.
   → the identity (`is`) test in `tests/test_actions.py` must FAIL.

Record the exact failing node ID for each. When inserting an import as part of a mutation,
put it **after** any `from __future__ import annotations` line — otherwise you get a
`SyntaxError` and a collection error, which is an inconclusive result, not a passing one.

Then restore and confirm clean:

```bash
git checkout -- src/ tests/
git status --short
```

**Must print nothing.**

### V5 — Negative control (last, after V4 is reverted)

```bash
set -o pipefail
./run.sh uv run pytest -q 2>&1 | tail -5
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

Re-run V1's mechanical check here too. This passes only if the implementation is present
*and* correct: V4 has just shown that removing any one of six load-bearing behaviors turns
the suite red, so a green run here is not something an empty implementation could produce.

### Deferred and explicitly NOT verified

State all of this in your final report and the session log. An unstated gap reads as a
covered one.

- **No native file dialog was ever opened**, by design — every test injects the fake. That
  the real `QFileDialog` appears, is native per-platform, and filters correctly is
  **manual, deferred** verification.
- **No real drag and drop from a file manager.** Drops are synthesised from `QMimeData`.
  Dragging from Finder/Explorer/Nautilus is manual and unverified.
- **No native window was displayed.** All Qt tests run under `QT_QPA_PLATFORM=offscreen`.
- **macOS and Windows are unverified.** CI is Ubuntu-only; the cross-platform matrix is
  Phase 15. In particular the `Cmd+Shift+F` mapping is asserted from the key sequence, not
  exercised on macOS.
- **No query executes.** Run stays disabled; execution is Phase 8. Do not describe the
  desktop app as functional.
- **No completion or call tips.** Phase 7. If you built any, you exceeded scope.
- **Clipboard assertions use the offscreen platform's clipboard**, which is not the system
  clipboard; real paste into another application is unverified.
- **CI is not proven by this plan.** It now runs on `dev` and genuinely honours the
  3.12/3.14 matrix, but remains unproven until a push actually triggers it.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished pyqt6-catalog-editor-formatter
```

This writes:

```text
/tmp/wherewolf/pyqt6-catalog-editor-formatter_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer pyqt6-catalog-editor-formatter`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/pyqt6-catalog-editor-formatter-review-*.md
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
   scripts/orchestration/clear-finished pyqt6-catalog-editor-formatter
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
   git add docs/review/pyqt6-catalog-editor-formatter-review-*.md
   git commit -m "docs(review): record pyqt6-catalog-editor-formatter review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished pyqt6-catalog-editor-formatter
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer pyqt6-catalog-editor-formatter` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed pyqt6-catalog-editor-formatter
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize pyqt6-catalog-editor-formatter
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/pyqt6-catalog-editor-formatter_finalized
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
scripts/orchestration/finalize pyqt6-catalog-editor-formatter
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/pyqt6-catalog-editor-formatter_finished
/tmp/wherewolf/pyqt6-catalog-editor-formatter_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
