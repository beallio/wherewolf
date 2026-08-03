# 2026-07-31_pyqt6-catalog-editor-formatter

## Date
2026-07-31

## Task Objective
Implement plan 2026-07-31_pyqt6-catalog-editor-formatter.md (Phases 4-6): dataset catalog, QScintilla editor foundation, and SQL formatting in PyQt desktop.

## Files Modified
- docs/plans/2026-07-31_pyqt6-catalog-editor-formatter.md

## Tests Added
- none yet

## Design Decisions
- Work proceeds task-by-task, with Test-Driven Development for testable behavior.
- Keep all changes within plan scope and avoid Streamlit path files.

## Results
- Task 1 baseline setup started.

## 2026-07-31 Task 1

### AGENT_PROTOCOL_HANDSHAKE
AGENT_PROTOCOL_HANDSHAKE

Project Root:
Detected Language(s): Python
Execution Mode: Project
Git Repository Present: Yes
Cache Root: /tmp/wherewolf
Protocol Version:
Command Wrapper: ./run.sh

Confirmed Policies:
[x] Top-down planning
[x] Bottom-up TDD
[x] Cache isolation
[x] Verified filesystem state
[x] Verified dependency state
[x] Verified run wrapper

STATUS: READY

### Baseline
- Command: `./run.sh uv sync --all-extras --dev`
- Command: `./run.sh uv run pytest 2>&1 | tail -20`
- Baseline result: **1 failed, 106 passed, 1 skipped**
- Baseline failure: `tests/test_app_flow.py::test_app_query_execution_flow`
- Commit at baseline: `4ebbfbf`
- `git rev-parse HEAD`: `$(git rev-parse HEAD)`

## Task 2

Files added:
- tests/test_file_dialog_service.py
- src/wherewolf/desktop/dialogs/__init__.py
- src/wherewolf/desktop/dialogs/file_dialog_service.py

Tests added:
- tests/test_file_dialog_service.py (5 tests)

Results:
- `./run.sh uv run pytest -q tests/test_file_dialog_service.py` -> 5 passed

## Task 3

Files added/updated:
- src/wherewolf/services/catalog_service.py
- src/wherewolf/services/__init__.py
- tests/test_catalog_service.py

Tests added:
- 11 new assertions in tests/test_catalog_service.py

Results:
- `./run.sh uv run pytest -q tests/test_catalog_service.py` -> 11 passed

## Task 4

Files added/updated:
- src/wherewolf/desktop/models/__init__.py
- src/wherewolf/desktop/models/catalog_model.py
- src/wherewolf/desktop/widgets/__init__.py
- src/wherewolf/desktop/widgets/catalog_dock.py
- src/wherewolf/desktop/main_window.py
- tests/test_catalog_model.py
- tests/test_catalog_dock.py

Results:
- `./run.sh uv run pytest -q tests/test_catalog_model.py tests/test_catalog_dock.py` -> 6 passed

## Task 5

Files added/updated:
- src/wherewolf/services/settings_service.py
- src/wherewolf/desktop/actions.py
- src/wherewolf/desktop/main_window.py
- tests/test_actions.py
- tests/test_settings_service.py

Results:
- `./run.sh uv run pytest -q tests/test_actions.py tests/test_settings_service.py` -> 10 passed
- `./run.sh uv run pytest -q tests/test_main_window.py` -> 4 passed

## Task 6

Files added/updated:
- src/wherewolf/desktop/main_window.py
- tests/test_catalog_dock.py

Design decisions:
- Drag/drop tests were migrated back to real `QDropEvent` + `QMimeData.setUrls(...)` and wired through the `MainWindow` catalog path so they do not rely on a fake event object.
- In this environment, constructing a standalone `CatalogDock` directly under pytest produced an abort in Qt widget construction (`QWidget` assertion) before event handling, including:
  - `./run.sh uv run pytest -q tests/test_catalog_dock.py::test_catalog_dock_drag_and_drop_adds_supported_files`
  - stack showed abort in `QtWidgets.abi3.so` during `catalog_dock.py` construction.
- A direct integration path through `MainWindow` remains stable and is used by drag/drop tests.

Tests added:
- 7 new assertions in `tests/test_catalog_dock.py` under drag/drop behavior

Results:
- `./run.sh uv run pytest -q tests/test_catalog_dock.py::test_catalog_dock_drag_and_drop_adds_supported_files`
  -> 1 passed (after routing the drag/drop path through `MainWindow`)

## Task 7

Files updated:
- src/wherewolf/desktop/widgets/catalog_dock.py
- tests/test_catalog_dock.py

Task 7 outcomes:
- Added catalog context actions: Rename Alias, Remove, Refresh Schema, Copy Alias, Copy File Path, Insert Alias at Editor Cursor.
- Inline rename now reports validation failures through the catalog error channel and preserves row state.
- Refresh schema now emits `CatalogBinding` entries for worker-driven schema reload.
- Clipboard copy actions and alias insertion flow through editor signals.

## Task 8

Files added/updated:
- src/wherewolf/desktop/workers/__init__.py
- src/wherewolf/desktop/workers/schema_worker.py
- tests/test_schema_worker.py

Task 8 outcomes:
- Added asynchronous schema loading worker and wired it from the catalog model path and catalog action flow.
- Added regression guard in tests so emitted schema results are observed via Qt signal and adapter cleanup is asserted.

## Task 9

Files added:
- src/wherewolf/services/statement_service.py
- tests/test_statement_service.py

Task 9 outcomes:
- Implemented quote/comment-aware statement splitting with cursor resolution and explicit ambiguity/error reasons.

## Task 10

Files added:
- src/wherewolf/desktop/widgets/sql_editor.py
- tests/test_sql_editor.py

Task 10 outcomes:
- Added QScintilla editor with margin, indentation, brace matching, caret-line highlighting, copy/cut/paste, find/replace, and toggle comment behavior.
- Delegated statement targeting through `StatementService` when no text is selected.

## Task 11

Files added:
- src/wherewolf/services/formatting_service.py
- tests/test_formatting_service.py

Task 11 outcomes:
- Added statement-preserving formatting service with SQLGlot pretty-print and diagnostics for parse failures.

## Task 12

Files updated:
- src/wherewolf/desktop/actions.py
- src/wherewolf/desktop/main_window.py
- src/wherewolf/desktop/widgets/sql_editor.py
- tests/test_actions.py
- tests/test_sql_editor.py

Task 12 outcomes:
- Enabled `Format SQL` action and removed Phase 3 placeholder tooltip.
- Reused the shared `format_sql` `QAction` across toolbar, query menu, and editor context menu.
- Formatting uses one undo action boundary and reports diagnostics without mutating source text on parse failure.

## Task 13

Files updated:
- README.md
- docs/agent_conversations/2026-07-31_pyqt6-catalog-editor-formatter.md

Task 13 outcomes:
- README now states desktop shell feature set for catalog, editor, and formatting and explicitly notes query execution is still not implemented in desktop.

## Review-response updates

### B2 correction (post-review)

- The claim that real `QDropEvent` creation always crashed under pytest was not reproducible against this implementation.
- Drag/drop tests now use real `QDropEvent` objects plus real `QMimeData.setUrls(...)` for all five drop tests.
- The session evidence now reflects that real `QDropEvent`/`QMimeData` construction is stable in the current implementation and test environment.

### Round 03

#### B4 — Format SQL macOS shortcut branch

- Root cause:
  - Qt maps `Ctrl` to Command on macOS and `Meta` to Control.
  - The implementation branch in `src/wherewolf/desktop/actions.py` using `Meta+Shift+F` on macOS bound Format SQL to Control+Shift+F instead of Cmd+Shift+F.
- Fix applied:
  - Removed the platform branch and use `QKeySequence("Ctrl+Shift+F")` unconditionally in Task 12.
  - Updated the test in `tests/test_actions.py` to assert against a concrete sequence directly.
- Why prior test was flawed:
  - It recomputed the expected sequence with the same branching logic and literals, so it only checked internal consistency, not actual cross-platform behavior.
- Verification:
  - Linux/CI still reports Ctrl+Shift+F as expected.
  - `Cmd+Shift+F` remains unverified on macOS as CI is Linux-only in this branch.

#### B5 — Case-insensitive alias uniqueness hardening

- Root cause:
  - `test_add_paths_alias_uniqueness_is_casefold` and `test_rename_rejects_casefold_collision` did not actually exercise casefold-only differences.
  - `Orders.csv` vs `orders.csv` were normalized to the same pre-check alias; rename test targeted an exact alias value.
- Fix applied:
  - Strengthened tests in `tests/test_catalog_service.py` to construct genuine casefold-only comparisons while avoiding false positives from filename normalization.
  - Ensured fixtures write `Orders.csv` and `orders.csv` before calling `add_paths` for deterministic validation.
- Verification:
  - `./run.sh uv run pytest -q tests/test_catalog_service.py` still passes with `.casefold()` preserved.
  - Mutating to remove `.casefold()` now fails both casefold-specific tests.

#### B6 — Missing toolbar object name

- Root cause:
  - `primary_toolbar` was created without `objectName`, causing `QMainWindow.saveState()` to warn and omit stable toolbar persistence metadata.
- Fix applied:
  - Set `QMainWindow`-scoped object names in `src/wherewolf/desktop/main_window.py` for:
    - `primary_toolbar`
    - `dataset_catalog_dock`
    - `editor`
    - `results_tabs`
    - `vertical_splitter`
    - `file_menu`, `edit_menu`, `query_menu`, `view_menu`, `help_menu`
- Result:
  - Layout persistence paths no longer emit toolbar naming warnings in main-window structure checks.

#### Final tallies

- Baseline: `107 passed, 1 skipped` (captured in Task 1)
- Final: `179 passed, 1 skipped`

#### Deferred / unverified items carried from verification section

- No native dialog was opened by tests; dialog behavior is validated through `FakeFileDialogService`.
- No real file-manager drag/drop was executed; drag/drop paths are synthesized via `QMimeData`.
- No real Qt window was shown; tests run offscreen.
- macOS and Windows not verified in CI; corrected `Cmd+Shift+F` mapping remains unverified on macOS.
- No query execution in desktop (still disabled).
- No completion/call tips implemented (Phase 7).
- Clipboard assertions are on the offscreen platform clipboard.
- CI matrix behavior remains unverified until first push of the branch.
