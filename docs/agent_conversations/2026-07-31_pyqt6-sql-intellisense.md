# Agent Session Log: PyQt6 Desktop Migration - Schema-aware IntelliSense (Phase 7)

- **Date**: 2026-07-31
- **Task Objective**: Implement Phase 7 schema-aware SQL completion and call tips for PyQt6 QScintilla SQL editor according to `docs/plans/2026-07-31_pyqt6-sql-intellisense.md`.
- **Baseline Commit**: `e1edcc2d3ca4aa917cbf0bf0fb206300438cf9e6`
- **Baseline Test Results**: 179 passed, 1 skipped

## Files Modified
- `docs/plans/2026-07-31_pyqt6-sql-intellisense.md` (initial commit of plan)
- `docs/agent_conversations/2026-07-31_pyqt6-sql-intellisense.md` (session log)
- `src/wherewolf/domain/models.py` (added CompletionContext, CompletionItem)
- `src/wherewolf/services/completion_context.py` (lexical cursor context detector)
- `src/wherewolf/services/sql_metadata.py` (dialect keyword and function metadata)
- `src/wherewolf/services/completion_service.py` (added call_tip for function call tips)
- `src/wherewolf/desktop/widgets/completion_adapter.py` (QScintilla presentation adapter)
- `src/wherewolf/desktop/actions.py` (added show_completion QAction)
- `src/wherewolf/services/settings_service.py` (completion threshold & enabled persistence)
- `src/wherewolf/desktop/widgets/sql_editor.py` (wired completion adapter & threshold/Ctrl+Space)
- `src/wherewolf/desktop/main_window.py` (wired show_completion to Query menu and synced catalog)

## Tests Added
- `tests/test_completion_models.py`
- `tests/test_completion_context.py`
- `tests/test_sql_metadata.py`
- `tests/test_completion_service.py`
- `tests/test_completion_adapter.py`

## Design Decisions
- Followed 12-task plan incrementally.
- Added dataclasses `CompletionContext` and `CompletionItem` with `__post_init__` empty label check.
- Built pure lexer `detect_context()` without SQLGlot for string/comment suppression and cursor classification.
- Implemented `sql_metadata.py` providing keywords and call-tip signatures for DuckDB and Spark.
- Implemented `SqlCompletionService` suggesting catalog aliases in `TABLE_REF` contexts.
- Implemented `alias.` column resolution with SQLGlot AST and lexical fallback on parse error.
- Implemented CTE discovery and derivable column resolution, including catalog table shadowing by CTEs.
- Implemented 6 ranking tiers, deterministic sorting, dialect identifier quoting (`"name"`), and function parens (`NAME(`).
- Implemented `call_tip()` finding unclosed function parens and reporting innermost function signature.
- Implemented `CompletionAdapter` mapping `CompletionItem` tuples to QScintilla `showUserList`, type icon markers, and replacing typed prefix on activation.
- Wired `show_completion` action into `DesktopActions`, `MainWindow` Query menu, and `SqlEditor` context menu (same QAction instance).
- Implemented completion threshold (default 2), toggle settings, `Ctrl+Space` override, and non-blocking schema None handling.

## Results
- Task 1 baseline: 179 passed, 1 skipped.
- Task 2 complete: `tests/test_completion_models.py` passing (3 tests).
- Task 3 complete: `tests/test_completion_context.py` passing (6 tests).
- Task 4 complete: `tests/test_sql_metadata.py` passing (3 tests).
- Task 5 complete: `tests/test_completion_service.py` passing (4 tests).
- Task 6 complete: `tests/test_completion_service.py` passing (13 tests total).
- Task 7 complete: `tests/test_completion_service.py` passing (17 tests total).
- Task 8 complete: `tests/test_completion_service.py` passing (20 tests total).
- Task 9 complete: `tests/test_completion_service.py` passing (24 tests total).
- Task 10 complete: `tests/test_completion_adapter.py` passing (3 tests).
- Task 11 complete: `tests/test_sql_editor.py` & `tests/test_settings_service.py` passing.
- Task 12 complete: `README.md` updated, full test suite and 25-run flake check passed cleanly with 0 crashes.

## Verification
- Quality gates: `ruff check`, `ruff format`, `ty check`, `pytest` (222 passed, 1 skipped).
- Flake check: 25 consecutive runs with 0 native crashes.
- TDD check: `scripts/check_tdd.sh` verified flat test structure for all new modules.

## Review Round 1 Resolution (2026-07-31)
- **Finding B1 (Completion threshold test gap)**: Added comprehensive tests in `tests/test_sql_editor.py` that spy on `SqlCompletionService.complete()`:
  1. Prefix shorter than threshold (1 char when threshold is 2) does not request completion (`spy.calls == 0`).
  2. Prefix at or above threshold (2 chars) requests completion (`spy.calls == 1`).
  3. `completion_enabled = False` prevents unforced completion requests but allows forced (`Ctrl+Space`) requests.
  4. Custom threshold (set to 3 via `SettingsService`) updates the trigger point so 2-char prefix no longer triggers, but 3-char prefix does.
- **Mutation Verification**: Verified that substituting `if False:` for the threshold check in `sql_editor.py:94` causes the new tests to fail (RED).
- **Observation N1**: Noted that `src/wherewolf/services/__init__.py` eagerly imports `settings_service` (which imports `PyQt6.QtCore`), transitively loading PyQt6 when importing completion service. Preserved without changes for this phase as PyQt6 is a required dependency.
