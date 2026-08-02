# Streamlit removal parity audit

This is a gate, not a claim that every desktop behavior has been manually exercised. Each
required criterion from migration-plan Section 21 is mapped to existing test node(s), `GAP`,
`PARTIAL`, or `MANUAL`. Every cited node was checked against the precise assertion; `PARTIAL`
records the exact remainder rather than overstating coverage.

## 21.1 Launch and desktop behavior

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| `wherewolf` opens one native desktop window | GAP | The current console target still reaches `wherewolf.cli:main`, which launches Streamlit; Task 4 supplies the red/green entry-point test. |
| no browser tab or local web server is started | MANUAL | Offscreen tests cannot prove that a real launch starts neither browser nor server. |
| `python -m wherewolf` opens the same application | GAP | `wherewolf.__main__` does not exist yet; Task 4 supplies the red/green entry-point test. |
| window geometry, docks, and splitter positions persist | PARTIAL | `test_main_window_restores_geometry_dock_layout_and_splitter_state` proves persisted dock, splitter, and height restoration; offscreen Qt constrains width and cannot prove real-screen position. |
| closing the main window shuts down workers cleanly or prompts when cancellation cannot complete immediately | `tests/test_main_window.py::test_main_window_close_waits_for_running_schema_workers`; `tests/test_main_window.py::test_main_window_close_calls_query_controller_shutdown` | Closes schema workers and invokes the query shutdown boundary. |
| normal DuckDB startup does not import/start Spark | `tests/test_cli.py::test_importing_desktop_application_is_free_of_pyspark` | An isolated subprocess asserts importing the desktop application loads no PySpark. |

## 21.2 Dataset workflow

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| Add Datasets opens the operating system's native multi-file dialog where supported | MANUAL | CI injects/fakes dialog behavior; it must not automate a real native dialog. |
| CSV, Parquet, JSON, JSON Lines, and XLSX filters are present | `tests/test_file_dialog_service.py::test_qt_file_dialog_service_filter_is_format_driven` | Asserts the format-derived Qt filter. |
| `.xls` is not falsely advertised | `tests/test_file_dialog_service.py::test_qt_file_dialog_service_filter_is_format_driven` | Filter assertion excludes unsupported legacy Excel. |
| drag/drop adds supported local files | `tests/test_catalog_dock.py::test_catalog_dock_drag_and_drop_adds_supported_files` | Drives a local-file drop through the dock. |
| duplicate resolved paths are not added twice | `tests/test_catalog_dock.py::test_catalog_dock_drag_and_drop_deduplicates_resolved_paths` | Adds a real path and a symlink resolving to it, then asserts one catalog entry. |
| aliases are editable and case-insensitively unique | `tests/test_catalog_dock.py::test_catalog_context_menu_rename_updates_alias_and_rejects_casefold_duplicate` | Drives context-menu rename, then rejects a casefold duplicate. |
| remove, copy alias/path, insert alias, and schema refresh work | `tests/test_catalog_dock.py::test_catalog_context_menu_copy_and_remove_actions`; `tests/test_catalog_dock.py::test_catalog_context_menu_refresh_schema_emits_binding`; `tests/test_schema_panel.py::test_schema_panel_insert_columns_single` | Each cited node asserts its named action. |
| schema failures show the underlying error | `tests/test_schema_panel.py::test_schema_panel_entry_schema_error` | Displays the entry-specific failure text. |

## 21.3 SQL editor

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| SQL syntax is highlighted | `tests/test_sql_editor.py::test_sql_editor_assigns_lexer` | Asserts the SQL lexer is installed. |
| line numbers, brace matching, undo/redo, find/replace, and toggle-comment work | PARTIAL | `test_sql_editor_line_margin_and_features_configured`, `test_sql_editor_undo_redo_cut_copy_paste`, `test_sql_editor_find_and_replace_all`, and `test_sql_editor_toggle_comment_round_trips_selection` cover all but independent brace-match behavior. |
| `Ctrl+Enter`/`Cmd+Enter` runs the selection or current statement | `tests/test_actions.py::test_build_actions_contains_expected_shortcuts_and_states`; `tests/test_sql_editor.py::test_text_to_run_prefers_selection_over_statement_lookup` | Verifies the Run shortcut and the exact selection/current-statement payload. |
| multiple statements are not silently discarded | `tests/test_execution_request_builder.py::test_build_multi_statement_preserves_all_statements` | Preserves every statement in the request. |
| `Ctrl+Space` shows completion | `tests/test_sql_editor.py::test_sql_editor_completion_threshold_and_ctrl_space` | Asserts the `Ctrl+Space` shortcut and forced request. |
| automatic completion can be enabled/disabled | `tests/test_sql_editor.py::test_sql_editor_completion_disabled_unforced_vs_forced` | Disabled automatic completion but preserves forced completion. |
| `FROM`/`JOIN` suggests catalog aliases | `tests/test_completion_service.py::test_complete_from_suggests_catalog_aliases`; `tests/test_completion_service.py::test_complete_join_suggests_catalog_aliases` | Separately asserts FROM and JOIN contexts. |
| `alias.` suggests the correct schema columns | `tests/test_completion_service.py::test_qualified_alias_returns_only_target_table_columns` | Asserts qualified columns are restricted to the target alias. |
| dialect keywords/functions are suggested | `tests/test_completion_service.py::test_complete_suggests_dialect_keywords_and_functions` | Invokes completion and asserts a dialect function result. |
| completion does not block while schema loads | `tests/test_sql_editor.py::test_sql_editor_gui_thread_never_blocked_with_none_schema` | Bounds forced completion with an unloaded schema to 0.5 seconds. |
| Format SQL exists on toolbar, menu, context menu, and shortcut | `tests/test_main_window.py::test_main_window_query_actions_initial_state_and_shared_instances`; `tests/test_main_window.py::test_format_action_is_shared_with_editor_context_action`; `tests/test_actions.py::test_build_actions_contains_expected_shortcuts_and_states` | Separately proves toolbar/menu, editor context, and shortcut. |
| formatting uses the source dialect and is one-step undoable | `tests/test_sql_editor.py::test_format_sql_one_undo_restores_entire_text`; `tests/test_formatting_service.py::test_dialect_is_preserved_for_duckdb_and_spark` | One undo restores text and the service verifies DuckDB/Spark output. |
| formatting errors leave SQL unchanged and display a diagnostic | `tests/test_sql_editor.py::test_format_error_leaves_text_unchanged_and_reports_diagnostic` | Asserts both unchanged text and diagnostic. |

## 21.4 Query lifecycle

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| one query can run at a time | `tests/test_query_controller.py::test_query_controller_second_run_refused_while_active` | Refuses a second active execution. |
| UI remains responsive during query execution | MANUAL | An offscreen event-loop test cannot measure real interactive responsiveness. |
| Cancel reports “requested” until the worker terminates | `tests/test_query_controller.py::test_query_controller_cancel_flow_transitions_to_cancellation_requested` | Asserts the intermediate cancellation-requested state. |
| DuckDB cancel affects only the active request connection | `tests/test_registry.py::test_duckdb_adapter_cancel_one_adapter_does_not_affect_another` | Proves request-scoped cancellation isolation. |
| history/export use the captured execution request | PARTIAL | `test_build_execution_request_captures_snapshot` proves immutable construction, but no integration test proves both consumers retain that exact request object. |
| errors are structured and visible | `tests/test_main_window.py::test_main_window_result_grid_integration` | Failed result becomes a typed visible Messages entry. |
| preview truncation is clearly indicated | `tests/test_main_window.py::test_main_window_query_result_details_and_metrics` | A truncated successful result visibly includes `truncated`. |

## 21.5 Results grid

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| individual cells are selectable | `tests/test_result_table_view.py::test_result_table_view_selection_and_copy` | Selects cells and verifies copied TSV. |
| rectangular ranges, rows, and columns are selectable | PARTIAL | `test_result_table_view_selection_and_copy` proves a rectangular cell range; explicit row/column selection gestures are not automated. |
| `Ctrl+C`/`Cmd+C` copies selected values as spreadsheet-compatible TSV | `tests/test_result_table_view.py::test_result_table_view_selection_and_copy` | Delivers Ctrl+C and asserts TSV clipboard text. |
| Copy with Column Names works | `tests/test_result_table_view.py::test_result_table_view_body_context_menu_actions` | Executes the body context action and asserts header-plus-data TSV. |
| column-name, quoted-column-name, and all-visible-column-name copy actions work | `tests/test_result_table_view.py::test_result_table_view_header_context_menu_actions` | Executes name, quoted-name, and all-visible-name actions; all-visible follows visual order and excludes hidden columns. |
| column names can be inserted into the editor | `tests/test_result_table_view.py::test_result_table_view_header_context_menu_actions` | Header action emits/inserts selected name. |
| clicking a header sorts ascending, descending, then restores query order | `tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_third_click_reset` | Asserts the three-state sort sequence. |
| sorting is type-aware | `tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_numeric_sorting` | Numeric values sort numerically. |
| active local sort is labelled “Sorted preview only.” | `tests/test_result_table_view.py::test_active_local_sort_discloses_that_only_the_preview_is_sorted` | Sort shows the visible notice and clearing sort hides it. |
| columns can be moved, resized, auto-sized, hidden, shown, and reset | PARTIAL | `test_result_table_view_column_operations` proves move, hide/show/reset, and auto-size; manual resize gesture is not automated. |
| clipboard serialization follows current visual row/column order | PARTIAL | `test_result_table_view_copy_respects_sort` proves visual row order; selected-cell copy after multi-column reordering is not automated. |
| preview search/filter can be cleared | `tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_search_and_filter` | Applies and clears the proxy filter. |
| explicit Apply Order to Query action is separate from local sorting | `tests/test_result_table_view.py::test_header_context_menu_apply_order`; `tests/test_result_table_view.py::test_local_sort_does_not_rerun_query` | Apply emits a query-order request, while local sorting submits no query. |

## 21.6 Supporting panels

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| Schema tab shows real schema or a real error | `tests/test_schema_panel.py::test_schema_panel_displays_columns_and_types`; `tests/test_schema_panel.py::test_schema_panel_error_display` | Separately asserts real column data and failure text. |
| Translation tab shows exact executable SQL | `tests/test_translation_panel.py::test_translation_panel_different_dialect` | Compares displayed translation directly with `ExecutionRequestBuilder` executable SQL. |
| Messages tab shows parse, translation, engine, and export errors | `tests/test_messages_panel.py::test_messages_panel_retains_parse_translation_and_export_diagnostics`; `tests/test_messages_panel.py::test_messages_panel_show_execution_error` | First node asserts parse/translation/export messages; second asserts structured engine error. |
| execution time, preview row count, engine, and truncation are visible | `tests/test_main_window.py::test_main_window_query_result_details_and_metrics` | Asserts engine, elapsed time, preview rows, and truncation. |

## 21.7 History and export

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| existing history file migrates without data loss in tested fixtures | `tests/test_history.py::test_v1_history_migrates_all_records_in_order_and_only_once` | Verifies ordered one-time migration. |
| history entries use IDs, not display labels | `tests/test_history_dock.py::test_history_dock_selects_duplicate_labels_by_stable_id` | Selects duplicate labels by stable ID. |
| restoring missing files is explicit | `tests/test_main_window.py::test_history_catalog_restore_loads_available_files_and_reports_missing_ones` | Missing file is reported in the status UI. |
| preview export works for CSV, XLSX, and Parquet | `tests/test_preview_export.py::test_preview_exports_reopen_with_columns_and_row_order` | Parameterized across all formats and reopens outputs. |
| selection export respects table visual order | `tests/test_preview_export.py::test_selection_export_reuses_visual_column_order` | Asserts visual column and cell order. |
| full DuckDB CSV/Parquet export writes directly to a file path | `tests/test_full_export.py::test_full_export_issues_copy_without_materialising_result` | Asserts direct `COPY ... TO` without materialising. |
| export cancellation/error does not corrupt an existing destination | PARTIAL | `test_full_export_publishes_handle_before_work_and_cancellation_preserves_destination` proves cancellation preserves existing bytes and cleans temp files; `test_full_export_failure_is_a_terminal_result_not_an_exception` proves error reporting but not destination preservation for an injected early error. |
| a source-file change between preview and full export produces a warning | `tests/test_full_export.py::test_full_xlsx_limit_and_source_warning` | Asserts source snapshot warning. |

## 21.8 Spark

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| Spark selector is available only when support is installed | `tests/test_main_window.py::test_engine_selector_disables_missing_spark_with_installation_guidance` | Missing support disables selector with install guidance. |
| session starts lazily | `tests/test_spark_engine.py::test_spark_engine_creates_a_memory_bounded_session_lazily_and_reuses_it` | Import/session creation occurs only at first use. |
| cancellation targets the request job group | `tests/test_spark_engine.py::test_spark_engine_cancels_only_its_request_job_group` | Asserts the request ID job group only. |
| `.json` and `.jsonl` semantics are tested separately | `tests/test_spark_engine.py::test_spark_engine_reads_json_array_and_json_lines` | Separate array and lines files execute independently. |
| full export does not unconditionally call `toArrow()` for an unbounded result | MANUAL | There is no Spark full-export adapter to execute; the DuckDB `COPY` guard cannot prove this Spark-specific criterion. |

## 21.9 Removal and licensing

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| no Streamlit code or dependency remains | GAP | Task 8 removes dependencies/config; Task 9 adds and runs the repository residue check. |
| package metadata and license files state `GPL-3.0-only` | `tests/test_licensing.py::test_license_file_is_gpl3`; `tests/test_licensing.py::test_pyproject_has_gpl3_license_and_files` | Separately checks GPL text and metadata/declarations. |
| pre-cutover MIT terms are accurately preserved in notices | MANUAL | Legal accuracy against the pre-cutover source cannot be proven by substring checks; human license review remains required. |
| About/Open-Source Licenses is present | `tests/test_main_window.py::test_main_window_help_menu_exposes_about_and_license_notice` | Opens the Help action and asserts GPL and pre-cutover MIT notice text. |
| wheel and source distribution include license files | MANUAL | The packaging declaration is unit-tested, but release artifact contents must be inspected after the final build. |

## Manual release gate

The following items require an actual human run before release: no browser/server, one real
native window, native multi-file dialog, UI responsiveness during query execution, platform
clipboard/window behavior, restored position/width, MIT notice accuracy, final artifact contents,
and cross-platform Windows/macOS validation. Spark full-export has
no implemented desktop adapter; its acceptance item is therefore not claimed by the DuckDB
streaming test.
