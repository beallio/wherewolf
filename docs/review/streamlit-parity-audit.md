# Streamlit removal parity audit

This is a gate, not a claim that every desktop behavior has been manually exercised. Each
required criterion from migration-plan Section 21 is mapped to one existing test node, `GAP`, or
`MANUAL`. Node IDs below were opened and checked for the asserted behavior before recording.

## 21.1 Launch and desktop behavior

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| `wherewolf` opens one native desktop window | GAP | The current console target still reaches `wherewolf.cli:main`, which launches Streamlit; Task 4 supplies the red/green entry-point test. |
| no browser tab or local web server is started | MANUAL | Offscreen tests cannot prove that a real launch starts neither browser nor server. |
| `python -m wherewolf` opens the same application | GAP | `wherewolf.__main__` does not exist yet; Task 4 supplies the red/green entry-point test. |
| window geometry, docks, and splitter positions persist | `tests/test_main_window.py::test_main_window_restores_geometry_dock_layout_and_splitter_state` | Saves and restores all three persistent layout values. |
| closing the main window shuts down workers cleanly or prompts when cancellation cannot complete immediately | `tests/test_main_window.py::test_main_window_close_calls_query_controller_shutdown` | Closing calls the query controller shutdown boundary. |
| normal DuckDB startup does not import/start Spark | `tests/test_cli.py::test_importing_desktop_application_is_free_of_streamlit_and_pyspark` | Subprocess asserts desktop import loads neither forbidden runtime. |

## 21.2 Dataset workflow

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| Add Datasets opens the operating system's native multi-file dialog where supported | MANUAL | CI injects/fakes dialog behavior; it must not automate a real native dialog. |
| CSV, Parquet, JSON, JSON Lines, and XLSX filters are present | `tests/test_file_dialog_service.py::test_qt_file_dialog_service_filter_is_format_driven` | Asserts the format-derived Qt filter. |
| `.xls` is not falsely advertised | `tests/test_file_dialog_service.py::test_qt_file_dialog_service_filter_is_format_driven` | Filter assertion excludes unsupported legacy Excel. |
| drag/drop adds supported local files | `tests/test_catalog_dock.py::test_catalog_dock_drag_and_drop_adds_supported_files` | Drives a local-file drop through the dock. |
| duplicate resolved paths are not added twice | `tests/test_catalog_dock.py::test_catalog_dock_drag_drop_deduplicates_resolved_paths` | Adds duplicate resolved paths and asserts deduplication. |
| aliases are editable and case-insensitively unique | `tests/test_catalog_dock.py::test_catalog_context_menu_rename_error_message` | Exercises rename validation error from the context menu. |
| remove, copy alias/path, insert alias, and schema refresh work | `tests/test_catalog_dock.py::test_catalog_context_menu_copy_and_remove_actions` | Covers copy and removal; refresh uses `tests/test_catalog_dock.py::test_catalog_dock_refresh_schema_updates_service_path`; insertion uses `tests/test_schema_panel.py::test_schema_panel_insert_columns_single`. |
| schema failures show the underlying error | `tests/test_schema_panel.py::test_schema_panel_entry_schema_error` | Displays the entry-specific failure text. |

## 21.3 SQL editor

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| SQL syntax is highlighted | `tests/test_sql_editor.py::test_sql_editor_assigns_lexer` | Asserts the SQL lexer is installed. |
| line numbers, brace matching, undo/redo, find/replace, and toggle-comment work | `tests/test_sql_editor.py::test_sql_editor_line_margin_and_features_configured` | Feature configuration plus dedicated `test_sql_editor_undo_redo_cut_copy_paste`, `test_sql_editor_find_and_replace_all`, and `test_sql_editor_toggle_comment_round_trips_selection`. |
| `Ctrl+Enter`/`Cmd+Enter` runs the selection or current statement | `tests/test_sql_editor.py::test_text_to_run_prefers_selection_over_statement_lookup` | Asserts selection/current-statement dispatch input. |
| multiple statements are not silently discarded | `tests/test_execution_request_builder.py::test_build_multi_statement_preserves_all_statements` | Preserves every statement in the request. |
| `Ctrl+Space` shows completion | `tests/test_sql_editor.py::test_sql_editor_completion_threshold_and_ctrl_space` | Asserts the `Ctrl+Space` shortcut and forced request. |
| automatic completion can be enabled/disabled | `tests/test_sql_editor.py::test_sql_editor_completion_disabled_unforced_vs_forced` | Disabled automatic completion but preserves forced completion. |
| `FROM`/`JOIN` suggests catalog aliases | `tests/test_completion_service.py::test_complete_from_suggests_catalog_aliases` | Asserts catalog suggestions in a FROM context. |
| `alias.` suggests the correct schema columns | `tests/test_completion_service.py::test_qualified_alias_returns_only_target_table_columns` | Asserts qualified columns are restricted to the target alias. |
| dialect keywords/functions are suggested | `tests/test_sql_metadata.py::test_get_dialect_functions_and_call_tips` | Verifies dialect function metadata and call tips. |
| completion does not block while schema loads | `tests/test_sql_editor.py::test_sql_editor_gui_thread_never_blocked_with_none_schema` | Exercises unloaded schema without blocking/raising. |
| Format SQL exists on toolbar, menu, context menu, and shortcut | `tests/test_sql_editor.py::test_main_window_show_completion_action_is_same_object_in_query_menu_and_editor` | Action sharing pattern is directly asserted for editor/menu; format sharing is asserted by `tests/test_main_window.py::test_format_action_is_shared_with_editor_context_action`. |
| formatting uses the source dialect and is one-step undoable | `tests/test_sql_editor.py::test_format_sql_one_undo_restores_entire_text` | One undo restores text; dialect behavior is asserted by `tests/test_formatting_service.py::test_dialect_is_preserved_for_duckdb_and_spark`. |
| formatting errors leave SQL unchanged and display a diagnostic | `tests/test_sql_editor.py::test_format_error_leaves_text_unchanged_and_reports_diagnostic` | Asserts both unchanged text and diagnostic. |

## 21.4 Query lifecycle

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| one query can run at a time | `tests/test_query_controller.py::test_query_controller_second_run_refused_while_active` | Refuses a second active execution. |
| UI remains responsive during query execution | MANUAL | An offscreen event-loop test cannot measure real interactive responsiveness. |
| Cancel reports “requested” until the worker terminates | `tests/test_query_controller.py::test_query_controller_cancel_flow_transitions_to_cancellation_requested` | Asserts the intermediate cancellation-requested state. |
| DuckDB cancel affects only the active request connection | `tests/test_registry.py::test_duckdb_adapter_cancel_one_adapter_does_not_affect_another` | Proves request-scoped cancellation isolation. |
| history/export use the captured execution request | `tests/test_execution_request_builder.py::test_build_execution_request_captures_snapshot` | Captures immutable request/source snapshot. |
| errors are structured and visible | `tests/test_main_window.py::test_main_window_result_grid_integration` | Failed result becomes a typed visible Messages entry. |
| preview truncation is clearly indicated | `tests/test_main_window.py::test_main_window_query_result_details_and_metrics` | Status presentation includes truncation/preview metrics. |

## 21.5 Results grid

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| individual cells are selectable | `tests/test_result_table_view.py::test_result_table_view_selection_and_copy` | Selects cells and verifies copied TSV. |
| rectangular ranges, rows, and columns are selectable | `tests/test_clipboard_serializers.py::test_serialize_contiguous_range` | Serializes a rectangular selection. |
| `Ctrl+C`/`Cmd+C` copies selected values as spreadsheet-compatible TSV | `tests/test_result_table_view.py::test_result_table_view_selection_and_copy` | Asserts tab-separated clipboard content. |
| Copy with Column Names works | `tests/test_result_table_view.py::test_result_table_view_header_context_menu_actions` | Executes header copy action. |
| column-name, quoted-column-name, and all-visible-column-name copy actions work | `tests/test_result_table_view.py::test_result_table_view_header_context_menu_actions` | Exercises all header actions. |
| column names can be inserted into the editor | `tests/test_result_table_view.py::test_result_table_view_header_context_menu_actions` | Header action emits/inserts selected name. |
| clicking a header sorts ascending, descending, then restores query order | `tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_third_click_reset` | Asserts the three-state sort sequence. |
| sorting is type-aware | `tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_numeric_sorting` | Numeric values sort numerically. |
| active local sort is labelled “Sorted preview only.” | `tests/test_result_table_view.py::test_local_sort_does_not_rerun_query` | Header-driven sort proves local behavior and checks preview-only label. |
| columns can be moved, resized, auto-sized, hidden, shown, and reset | `tests/test_result_table_view.py::test_result_table_view_column_operations` | Exercises the column-operation menu actions. |
| clipboard serialization follows current visual row/column order | `tests/test_result_table_view.py::test_result_table_view_copy_respects_sort` | Copy follows the sorted visual grid. |
| preview search/filter can be cleared | `tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_search_and_filter` | Applies and clears the proxy filter. |
| explicit Apply Order to Query action is separate from local sorting | `tests/test_result_table_view.py::test_header_context_menu_apply_order` | Asserts explicit apply action is distinct. |

## 21.6 Supporting panels

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| Schema tab shows real schema or a real error | `tests/test_schema_panel.py::test_schema_panel_error_display` | Covers display of both schema panel states. |
| Translation tab shows exact executable SQL | `tests/test_translation_panel.py::test_translation_panel_different_dialect` | Asserts the translated executable SQL text. |
| Messages tab shows parse, translation, engine, and export errors | `tests/test_messages_panel.py::test_messages_panel_show_execution_error` | Structured error display; translation diagnostic is `tests/test_translation_panel.py::test_translation_panel_shows_diagnostics`. |
| execution time, preview row count, engine, and truncation are visible | `tests/test_main_window.py::test_main_window_query_result_details_and_metrics` | Asserts engine, duration, and preview details in UI state. |

## 21.7 History and export

| Required criterion | Evidence | Reason |
| --- | --- | --- |
| existing history file migrates without data loss in tested fixtures | `tests/test_history.py::test_v1_history_migrates_all_records_in_order_and_only_once` | Verifies ordered one-time migration. |
| history entries use IDs, not display labels | `tests/test_history_dock.py::test_history_dock_selects_duplicate_labels_by_stable_id` | Selects duplicate labels by stable ID. |
| restoring missing files is explicit | `tests/test_main_window.py::test_history_catalog_restore_loads_available_files_and_reports_missing_ones` | Missing file is reported in the status UI. |
| preview export works for CSV, XLSX, and Parquet | `tests/test_preview_export.py::test_preview_exports_reopen_with_columns_and_row_order` | Parameterized across all formats and reopens outputs. |
| selection export respects table visual order | `tests/test_preview_export.py::test_selection_export_reuses_visual_column_order` | Asserts visual column and cell order. |
| full DuckDB CSV/Parquet export writes directly to a file path | `tests/test_full_export.py::test_full_export_issues_copy_without_materialising_result` | Asserts direct `COPY ... TO` without materialising. |
| export cancellation/error does not corrupt an existing destination | `tests/test_export_controller.py::test_full_export_publishes_handle_before_work_and_cancellation_preserves_destination` | Existing bytes and temp-file cleanup are asserted. |
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
| package metadata and license files state `GPL-3.0-only` | `tests/test_licensing.py::test_pyproject_has_gpl3_license_and_files` | Asserts metadata and license-file declaration. |
| pre-cutover MIT terms are accurately preserved in notices | `tests/test_licensing.py::test_notice_text_mentions_gpl_and_mit_history` | Asserts GPL and MIT history notice content. |
| About/Open-Source Licenses is present | GAP | No existing test or desktop action proves an About/licenses UI. |
| wheel and source distribution include license files | GAP | No packaging-artifact test currently builds and inspects both distributions. |

## Manual release gate

The following items require an actual human run before release: no browser/server, one real
native window, native multi-file dialog, UI responsiveness during query execution, platform
clipboard/window behavior, and cross-platform Windows/macOS validation. Spark full-export has
no implemented desktop adapter; its acceptance item is therefore not claimed by the DuckDB
streaming test.
