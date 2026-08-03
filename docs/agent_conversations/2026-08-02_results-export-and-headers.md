# Results export and headers implementation

Date: 2026-08-02
Objective: Implement `docs/plans/2026-08-02_results-export-and-headers.md` on
`feat/results-export-and-headers`.

## Files modified

- `src/wherewolf/desktop/main_window.py`
- `src/wherewolf/services/settings_service.py`
- `src/wherewolf/services/execution_request_builder.py`
- `src/wherewolf/services/export_destination.py`
- `src/wherewolf/desktop/dialogs/file_dialog_service.py`
- `src/wherewolf/desktop/models/polars_table_model.py`
- `src/wherewolf/desktop/widgets/result_table_view.py`
- `src/wherewolf/desktop/widgets/sql_editor.py`
- Tests covering the six implementation tasks.
- `docs/review/manual-acceptance-checklist.md` received the deferred manual badge/font checks.

## Design decisions

- The starter query is `SELECT * FROM "select"` with no SQL row limit. Fresh preview
  requests use 1000 rows.
- Export scope remains a single selector plus the Export button; Query-menu actions and
  shortcuts remain available. The save filter is now exactly one selected extension.
- Header badges use `INT`, `FLOAT`, `TXT`, `DATE`, `BOOL`, `NUM`, or `OTHER`. They are
  exposed through `UserRole`; `DisplayRole` remains the plain column name and the tooltip
  retains the full Polars dtype.
- QScintilla receives the selected font through `lexer.setFont(font)`, covering every
  per-style font while preserving persisted Preferences behavior.
- Preview input is a `QLineEdit` with object name `preview_limit_selector`, validator and
  visible invalid-state styling. Valid values are 10 through 100000; invalid text does not
  replace the last valid request value or persisted setting.

## Verification evidence

- Auto-fill after adding `select.csv`: `SELECT * FROM "select"`; existing `SELECT user_query`
  remains unchanged. A fresh `SettingsService` and an implicit `ExecutionRequest` both report
  preview limit `1000`.
- At 1024px, the named results-row controls are
  `preview_filter_input`, `export_format_selector`, `export_scope_selector`, and
  `export_button`, all visible. `export_preview_button`, `export_full_button`, and
  `export_selection_button` are absent. Query action texts are `Export Preview…`,
  `Export Full Results…`, and `Export Selection…`.
- The exact save-dialog filters are `Export files (*.csv)`, `Export files (*.parquet)`, and
  `Export files (*.xlsx)`. The Parquet Export button path wrote two rows, whose first rows were
  `[{'id': 1}, {'id': 2}]`, and `pl.read_parquet` read them back.
- Result badges for integer/string/date/boolean columns were
  `['INT', 'TXT', 'DATE', 'BOOL']`; tooltips were `count: Int64`, `name: String`,
  `started: Date`, and `active: Boolean`.
- After `set_font_size(28)`, widget, default lexer, keyword lexer, and identifier lexer fonts
  all reported 28 points. The persisted setting and a new `SqlEditor` also reported/restored 28.
- Preview input behavior: `500` and `50000` persisted; `5`, `999999`, `abc`, and empty text
  showed the invalid state, left the persisted value at the last valid value, and produced a
  request using that last valid value. `10` and `100000` were accepted. A fresh profile starts
  at 1000. No large-preview performance benchmark was run; 100000 is a typo guard, not a
  performance-tested maximum.

## Negative controls

Each mutation was printed or diffed before running the full suite, then restored:

| Mutation | Guarding test | Result |
| --- | --- | --- |
| Restore `LIMIT 10` in auto-fill | `test_main_window_fills_starter_query_for_first_dataset_when_editor_is_empty` | 1 failed, 432 passed, 7 deselected |
| Re-add `export_preview_button` as a `QToolButton` | `test_main_window_results_expose_export_controls_and_query_actions_at_1024px` | 1 failed, 432 passed, 7 deselected |
| List every export format in the save filter | filter destination tests | 4 failed, 429 passed, 7 deselected |
| Return `TYPE` for every dtype badge | `test_result_table_view_headers_show_distinct_dtype_badges_and_tooltips` | 1 failed, 432 passed, 7 deselected |
| Remove `lexer.setFont(font)` | `test_sql_editor_font_settings_are_restored_and_saved` | 1 failed, 432 passed, 7 deselected |
| Drop preview range validation | `test_main_window_preview_limit_text_box_validates_and_uses_last_valid_value` | 1 failed, 432 passed, 7 deselected |

The captured negative-control logs are in `/tmp/wherewolf/negative-task{1..6}.log`.

## Results

Baseline: 430 passed, 7 deselected.

Final implementation suite: 433 passed, 7 deselected.

Quality gates passed through `scripts/orchestration/run-quality-gates`, including ruff,
formatting, `ty check src/`, pytest, and review-note deletion protection. The additional
plan-required `./run.sh uv run ty check .` also passed. The unrelated pre-existing
`feature-ideation-workbench-depth.md` remains untracked and untouched.
