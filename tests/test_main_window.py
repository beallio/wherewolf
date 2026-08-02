import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import polars as pl
import pytest
from PyQt6.QtCore import QCoreApplication, QSettings, Qt
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
)

from wherewolf.desktop import main_window
from wherewolf.desktop.dialogs import FakeFileDialogService
from wherewolf.desktop.main_window import MainWindow
from wherewolf.domain import (
    CatalogBinding,
    ColumnSchema,
    EngineKind,
    ExecutionRequest,
    ExecutionStatus,
    QueryResult,
    SchemaResult,
    SourceFormat,
)
from wherewolf.services import CatalogService, ExportFormat, SettingsService
from wherewolf.storage import HistoryManager


def _configure_qsettings_path(tmp_path: Path) -> SettingsService:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    settings = QSettings(SettingsService.ORGANIZATION, SettingsService.APPLICATION)
    settings.clear()
    return SettingsService(settings)


def test_main_window_structure(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    menu_bar = window.menuBar()

    assert isinstance(window, QMainWindow)
    assert menu_bar is not None
    assert isinstance(window.main_toolbar, QToolBar)
    assert window.dataset_catalog_dock.objectName() == "dataset_catalog_dock"
    assert isinstance(window.dataset_catalog_dock, QDockWidget)
    assert window.main_toolbar.objectName() == "primary_toolbar"
    assert isinstance(window.findChild(QSplitter), QSplitter)
    assert isinstance(window.findChild(QTabWidget), QTabWidget)
    assert isinstance(window.status_bar, QStatusBar)

    for toolbar in window.findChildren(QToolBar):
        assert toolbar.objectName()

    assert len(window.findChildren(QToolBar)) == 1

    for dock in window.findChildren(QDockWidget):
        assert dock.objectName()

    menu_titles = [action.text() for action in menu_bar.actions()]
    assert menu_titles == ["File", "Edit", "Query", "View", "Help"]


def test_main_window_help_menu_exposes_about_and_license_notice(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    shown: dict[str, str] = {}

    def capture_about(_parent, title: str, text: str) -> None:
        shown["title"] = title
        shown["text"] = text

    monkeypatch.setattr(main_window.QMessageBox, "about", capture_about)
    about_action = next(action for action in window.help_menu.actions() if action.text() == "About")

    about_action.trigger()

    assert shown["title"] == "About Wherewolf"
    assert "GPL-3.0-only" in shown["text"]
    assert "build" in shown["text"]
    assert "MIT" not in shown["text"]


def test_engine_selector_disables_missing_spark_with_installation_guidance(
    qtbot, monkeypatch
) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)

    window = MainWindow()
    qtbot.addWidget(window)

    selector = window.findChild(QComboBox, "engine_selector")
    assert selector is not None
    spark_index = selector.findText("Spark", Qt.MatchFlag.MatchStartsWith)
    assert spark_index >= 0
    item = cast(QStandardItemModel, selector.model()).item(spark_index)
    assert item is not None
    assert item.isEnabled() is False
    assert "wherewolf[spark]" in item.text()
    assert selector.currentData() is EngineKind.DUCKDB


def test_main_window_engine_selector_offers_only_execution_backends(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    selector = window.engine_selector

    assert tuple(EngineKind) == (EngineKind.DUCKDB, EngineKind.SPARK)
    assert [selector.itemData(index) for index in range(selector.count())] == [
        EngineKind.DUCKDB,
        EngineKind.SPARK,
    ]


def test_input_dialect_selector_exposes_all_supported_source_dialects(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    selector = window.input_dialect_selector

    assert [selector.itemText(index) for index in range(selector.count())] == [
        "DuckDB",
        "Spark",
        "Azure SQL",
        "Oracle",
        "PostgreSQL",
    ]
    assert [selector.itemData(index) for index in range(selector.count())] == [
        "duckdb",
        "spark",
        "tsql",
        "oracle",
        "postgres",
    ]


def test_bare_main_window_does_not_touch_user_history(qtbot, monkeypatch, tmp_path: Path) -> None:
    """Default construction must use pytest-isolated persistence, never ~/.wherewolf."""
    user_history_path = Path.home() / ".wherewolf" / "history.json"
    ensure_storage = HistoryManager._ensure_storage

    def assert_isolated_storage(manager: HistoryManager) -> None:
        assert manager.storage_path != user_history_path
        ensure_storage(manager)

    monkeypatch.setattr(HistoryManager, "_ensure_storage", assert_isolated_storage)

    window = MainWindow()
    qtbot.addWidget(window)

    assert window.history_manager.storage_path != user_history_path
    assert Path(window._settings_service._settings.fileName()).is_relative_to(tmp_path)


def test_main_window_query_actions_initial_state_and_shared_instances(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    run_action = window.desktop_actions.run
    cancel_action = window.desktop_actions.cancel
    format_action = window.desktop_actions.format_sql

    assert not run_action.isEnabled()
    assert not cancel_action.isEnabled()
    assert format_action.isEnabled()

    query_actions = window.query_menu.actions()
    assert run_action in query_actions
    assert cancel_action in query_actions
    assert format_action in query_actions

    assert run_action is query_actions[0]
    assert run_action is window.main_toolbar.actions()[0]
    assert cancel_action is query_actions[1]
    assert cancel_action is window.main_toolbar.actions()[1]
    assert format_action is query_actions[2]
    assert format_action is window.main_toolbar.actions()[2]

    editor_context = window.editor._setup_context_menu
    assert editor_context is not None


def test_main_window_edit_menu_exposes_the_editor_actions(qtbot) -> None:
    """The menubar must expose the same actions the editor uses in its context menu."""
    window = MainWindow()
    qtbot.addWidget(window)

    actions = [action for action in window.edit_menu.actions() if not action.isSeparator()]

    assert actions
    assert [action.text() for action in actions] == [
        "Undo",
        "Redo",
        "Cut",
        "Copy",
        "Paste",
        "Select All",
        "Find / Replace…",
        "Toggle Comment",
    ]
    assert actions[:5] == list(window.editor.edit_actions[:5])
    assert window.select_all_action.shortcut().toString() == "Ctrl+A"
    assert window.find_replace_action.shortcut().toString() == "Ctrl+F"
    assert window.editor.edit_actions[-1].shortcut().toString() == "Ctrl+/"


def test_main_window_find_replace_dialog_changes_editor_text(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.editor.setText("SELECT old_value, old_value")

    window.find_replace_action.trigger()
    dialog = window.find_replace_dialog
    dialog.find_input.setText("old_value")
    dialog.replace_input.setText("new_value")
    dialog.replace_all_button.click()

    assert window.editor.text() == "SELECT new_value, new_value"


def test_main_window_preview_filter_reduces_rows_and_clear_restores_them(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.result_table_view.set_frame(pl.DataFrame({"name": ["Ada", "Grace", "Ada Lovelace"]}))

    assert window.result_table_view.proxy_model().rowCount() == 3
    window.preview_filter_input.setText("ada")
    assert window.result_table_view.proxy_model().rowCount() == 2
    window.clear_preview_filter_action.trigger()
    assert window.result_table_view.proxy_model().rowCount() == 3


def test_main_window_exports_selected_cells_in_visual_column_order(tmp_path: Path, qtbot) -> None:
    destination = tmp_path / "selection"
    window = MainWindow(
        file_dialog_service=FakeFileDialogService(paths=(), export_path=destination)
    )
    qtbot.addWidget(window)
    grid = window.result_table_view
    grid.set_frame(pl.DataFrame({"a": [1, 2], "b": ["one", "two"]}))
    grid.move_column(1, 0)
    grid.selectRow(0)

    window.desktop_actions.export_selection.trigger()

    assert pl.read_csv(destination.with_suffix(".csv")).to_dicts() == [{"b": "one", "a": 1}]


def test_main_window_routes_editor_diagnostic_to_messages_tab(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.editor._update_status("bad SQL")

    text, severity = window.messages_panel.message_at(0)
    assert "bad SQL" in text
    assert severity == "info"


def test_main_window_editor_shows_call_tip_for_known_function(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    shown: list[str] = []
    monkeypatch.setattr(
        window.editor,
        "SendScintilla",
        lambda _message, _position, text: shown.append(text.decode()),
    )

    window.editor.setText("SELECT COUNT(")
    window.editor.setCursorPosition(0, len("SELECT COUNT("))
    window.editor.request_completion(forced=True)

    assert shown and "COUNT" in shown[-1]


def test_main_window_preferences_persist_and_change_editor_font(tmp_path: Path, qtbot) -> None:
    settings = _configure_qsettings_path(tmp_path / "preferences-dialog")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    dialog.font_size.setValue(18)
    dialog.completion_enabled.setChecked(False)
    dialog.completion_threshold.setValue(4)
    dialog.accept()

    assert settings.restore_editor_font_size() == 18
    assert settings.restore_completion_enabled() is False
    assert settings.restore_completion_threshold() == 4
    assert window.editor.font_size == 18


def test_main_window_empty_catalog_gates_run_and_added_dataset_enables_it(
    tmp_path: Path, qtbot
) -> None:
    csv_file = tmp_path / "people.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow(file_dialog_service=FakeFileDialogService(paths=(csv_file,)))
    qtbot.addWidget(window)

    assert not window.desktop_actions.run.isEnabled()
    assert "Please add a dataset" in window.empty_catalog_banner.text()
    window.desktop_actions.add_datasets.trigger()

    assert window.desktop_actions.run.isEnabled()
    assert "Wherewolf" in window.windowTitle()
    assert "Added `people` to catalog." in window.status_bar.currentMessage()


def test_main_window_explains_truncation_and_keeps_raw_error_details_collapsed(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    request = ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=1,
        submitted_at=datetime.now(UTC),
    )
    truncated = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"x": [1]}),
        execution_seconds=0.1,
        preview_row_count=1,
        total_row_count=None,
        truncated=True,
        completed_at=datetime.now(UTC),
    )
    window._on_query_result_ready(truncated, request)
    assert not window.result_truncation_notice.isHidden()
    failed = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.1,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="SyntaxError",
        error_message="bad syntax",
        error_detail="raw backend traceback",
    )
    window._on_query_result_ready(failed, request)
    assert not window.messages_panel.error_details_toggle.isHidden()
    assert window.messages_panel.error_details.isHidden()


def test_main_window_help_actions_and_catalog_reveal_command(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "people.csv"
    source.write_text("id\n1\n")
    window = MainWindow()
    qtbot.addWidget(window)
    window.catalog.add_paths((source,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)
    window.catalog.view.selectRow(0)

    assert {action.text() for action in window.help_menu.actions()} >= {
        "About",
        "Documentation",
        "Open-Source Licenses",
    }
    command = window.catalog.reveal_command(source)
    assert str(source.parent) in command or str(source) in command


def test_main_window_about_identifies_gpl_build_without_mit(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    shown: list[str] = []
    monkeypatch.setattr(main_window.QMessageBox, "about", lambda _p, _t, text: shown.append(text))

    window._show_about()

    assert "wherewolf" in shown[0]
    assert "build" in shown[0]
    assert "GPL-3.0-only" in shown[0]
    assert "MIT" not in shown[0]


def test_main_window_schema_panel_shows_schema_after_adding_dataset(tmp_path: Path, qtbot) -> None:
    csv_file = tmp_path / "people.csv"
    csv_file.write_text("id,name\n1,Ada\n")
    window = MainWindow(file_dialog_service=FakeFileDialogService(paths=(csv_file,)))
    qtbot.addWidget(window)

    window.desktop_actions.add_datasets.trigger()

    qtbot.waitUntil(lambda: window.schema_panel.column_count_rows() == 2)
    assert [window.schema_panel.cell_text(row, 0) for row in range(2)] == ["id", "name"]
    assert [window.schema_panel.cell_text(row, 1) for row in range(2)] == ["BIGINT", "VARCHAR"]


def test_main_window_schema_selector_switches_between_loaded_datasets(
    tmp_path: Path, qtbot
) -> None:
    first_path = tmp_path / "customers.csv"
    second_path = tmp_path / "loans.csv"
    first_path.write_text("id\n1\n")
    second_path.write_text("amount\n100\n")
    service = CatalogService()
    added = service.add_paths((first_path, second_path)).added
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    window._on_schema_result(SchemaResult(added[0].id, (ColumnSchema("id", "BIGINT"),)))
    window._on_schema_result(SchemaResult(added[1].id, (ColumnSchema("amount", "DOUBLE"),)))

    selector = window.schema_panel.dataset_selector
    selector.setCurrentText(added[0].alias)
    assert window.schema_panel.cell_text(0, 0) == "id"
    selector.setCurrentText(added[1].alias)
    assert window.schema_panel.cell_text(0, 0) == "amount"


def test_main_window_translation_tab_transpiles_current_editor_text(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    target_index = window.translation_target_selector.findData("spark")
    assert target_index >= 0
    window.translation_target_selector.setCurrentIndex(target_index)
    window.editor.setText("SELECT IFNULL(value, 0) FROM users")

    assert window.translation_panel.translated_text() == "SELECT\n  COALESCE(value, 0)\nFROM users"


def test_main_window_translation_target_uses_friendly_dialect_names(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    target = window.translation_target_selector
    azure_sql_index = target.findText("Azure SQL")

    assert azure_sql_index >= 0
    assert target.itemData(azure_sql_index) == "tsql"
    assert target.itemText(target.findData("duckdb")) == "DuckDB"

    target.setCurrentIndex(azure_sql_index)
    window.editor.setText("SELECT * FROM users LIMIT 1")

    assert "TOP 1" in window.translation_panel.translated_text().upper()


def test_main_window_transpiles_selected_input_dialect_before_execution(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(window.query_controller, "execute", submitted.append)
    window.editor.setText("SELECT TOP 10 * FROM users")
    window.desktop_actions.run.setEnabled(True)  # isolated request-builder test without a catalog

    source_index = window.input_dialect_selector.findData("tsql")
    assert source_index >= 0
    window.input_dialect_selector.setCurrentIndex(source_index)
    window.desktop_actions.run.trigger()

    assert len(submitted) == 1
    assert submitted[0].source_dialect == "tsql"
    assert submitted[0].executable_sql != submitted[0].original_sql
    assert "LIMIT 10" in submitted[0].executable_sql


@pytest.mark.parametrize(
    ("sql", "construct"),
    (
        ("SELECT name FROM people WHERE ROWNUM <= 3", "ROWNUM"),
        ("SELECT SYSDATE FROM DUAL", "DUAL"),
    ),
)
def test_main_window_reports_unsupported_oracle_constructs(
    qtbot, monkeypatch, sql, construct
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(window.query_controller, "execute", submitted.append)
    window.editor.setText(sql)
    window.desktop_actions.run.setEnabled(True)

    source_index = window.input_dialect_selector.findData("oracle")
    assert source_index >= 0
    window.input_dialect_selector.setCurrentIndex(source_index)
    window.desktop_actions.run.trigger()

    assert submitted == []
    message, severity = window.messages_panel.message_at(0)
    assert severity == "error"
    assert construct in message
    assert "Oracle" in message
    assert "cannot run" in message


def test_main_window_preview_limit_and_theme_are_reachable_and_persisted(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    settings = _configure_qsettings_path(tmp_path / "preferences")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(window.query_controller, "execute", submitted.append)
    window.desktop_actions.run.setEnabled(True)
    window.preview_limit_selector.setValue(250)
    window.editor_theme_selector.setCurrentText("Light")
    window.editor.setText("SELECT 1")
    window.desktop_actions.run.setEnabled(True)  # isolated request-builder test without a catalog

    window.desktop_actions.run.trigger()

    assert submitted[0].preview_limit == 250
    assert settings.restore_preview_limit() == 250
    assert settings.restore_editor_theme() == "Light"


def test_main_window_fills_starter_query_for_first_dataset_when_editor_is_empty(
    tmp_path: Path, qtbot
) -> None:
    csv_file = tmp_path / "select.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow(file_dialog_service=FakeFileDialogService(paths=(csv_file,)))
    qtbot.addWidget(window)

    window.desktop_actions.add_datasets.trigger()

    assert window.editor.text() == 'SELECT * FROM "select" LIMIT 10'


def test_main_window_never_overwrites_existing_editor_text_when_adding_dataset(
    tmp_path: Path, qtbot
) -> None:
    csv_file = tmp_path / "people.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow(file_dialog_service=FakeFileDialogService(paths=(csv_file,)))
    qtbot.addWidget(window)
    window.editor.setText("SELECT user_query")

    window.desktop_actions.add_datasets.trigger()

    assert window.editor.text() == "SELECT user_query"


@pytest.mark.parametrize("export_format", (ExportFormat.PARQUET, ExportFormat.XLSX))
def test_main_window_exports_selected_format_to_readable_artifact(
    tmp_path: Path, qtbot, export_format: ExportFormat
) -> None:
    destination = tmp_path / "result"
    window = MainWindow(
        file_dialog_service=FakeFileDialogService(paths=(), export_path=destination)
    )
    qtbot.addWidget(window)
    request_id = uuid4()
    request = ExecutionRequest(
        request_id=request_id,
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=100,
        submitted_at=datetime.now(UTC),
    )
    result = QueryResult(
        request_id=request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"id": [1, 2]}),
        execution_seconds=0.01,
        preview_row_count=2,
        total_row_count=2,
        truncated=False,
        completed_at=datetime.now(UTC),
    )
    window._on_query_result_ready(result, request)

    format_index = window.export_format_selector.findData(export_format)
    assert format_index >= 0
    window.export_format_selector.setCurrentIndex(format_index)
    with qtbot.waitSignal(window.export_controller.result_ready, timeout=3000):
        window.desktop_actions.export_preview.trigger()

    artifact = destination.with_suffix(f".{export_format.value}")
    assert artifact.exists()
    reader = pl.read_parquet if export_format is ExportFormat.PARQUET else pl.read_excel
    assert reader(artifact).to_dicts() == [{"id": 1}, {"id": 2}]


def test_format_action_is_shared_with_editor_context_action(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.editor._format_action is window.desktop_actions.format_sql


def test_main_window_recoverable_from_corrupt_settings(qtbot, tmp_path: Path) -> None:
    service = _configure_qsettings_path(tmp_path / "corrupt")
    service.save_window_state(b"state-value")
    service._settings.setValue(service.window_geometry_key, "garbage")

    window = MainWindow(settings_service=service)
    qtbot.addWidget(window)
    assert isinstance(window, QMainWindow)


def test_main_window_close_cleans_top_level_widgets(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.close()
    app = QCoreApplication.instance()
    assert app is not None
    app.processEvents()
    assert isinstance(app, QApplication)
    top_levels = [w for w in app.topLevelWidgets() if isinstance(w, QMainWindow)]
    assert not any(widget is window for widget in top_levels)


def test_main_window_run_and_cancel_action_objects_are_shared(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    toolbar_run = window.main_toolbar.actions()[0]
    menu_run = window.query_menu.actions()[0]
    assert toolbar_run is menu_run is window.desktop_actions.run

    toolbar_cancel = window.main_toolbar.actions()[1]
    menu_cancel = window.query_menu.actions()[1]
    assert toolbar_cancel is menu_cancel is window.desktop_actions.cancel


def test_main_window_run_empty_editor_shows_status_and_starts_nothing(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.editor.setText("   \n\t ")
    window.desktop_actions.run.setEnabled(True)

    window.desktop_actions.run.trigger()

    assert window.query_controller.status.name == "IDLE"
    assert (
        "No SQL statement to run" in window.status_bar.currentMessage()
        or "empty" in window.status_bar.currentMessage().lower()
        or "statement" in window.status_bar.currentMessage().lower()
    )


def test_history_record_restore_updates_editor_without_execution_or_catalog(
    tmp_path: Path, qtbot
) -> None:
    history = HistoryManager(storage_path=tmp_path / "history.json")
    history.add_entry("duckdb", "SELECT restored_sql")
    record = history.get_all()[0]
    window = MainWindow(history_manager=history)
    qtbot.addWidget(window)
    initial_catalog = window._catalog_service.entries

    window.history_dock.record_selected.emit(record)

    assert window.editor.text() == "SELECT restored_sql"
    assert window.query_controller.status is ExecutionStatus.IDLE
    assert window._catalog_service.entries == initial_catalog


def test_history_catalog_restore_loads_available_files_and_reports_missing_ones(
    tmp_path: Path, qtbot
) -> None:
    existing = tmp_path / "available.csv"
    existing.write_text("id\n1\n")
    missing = tmp_path / "missing.csv"
    history = HistoryManager(storage_path=tmp_path / "history.json")
    history.add_entry(
        "duckdb",
        "SELECT * FROM available",
        catalog={"available": str(existing), "missing": str(missing)},
    )
    window = MainWindow(history_manager=history)
    qtbot.addWidget(window)

    window.history_dock.record_selected.emit(history.get_all()[0])

    qtbot.waitUntil(lambda: len(window._catalog_service.entries) == 1)
    assert window._catalog_service.entries[0].path == existing.resolve()
    assert str(missing) in window.status_bar.currentMessage()


def test_main_window_restores_geometry_dock_layout_and_splitter_state(
    tmp_path: Path, qtbot
) -> None:
    service = _configure_qsettings_path(tmp_path / "restore")
    original = MainWindow(settings_service=service)
    qtbot.addWidget(original)
    original.resize(960, 720)
    original.show()
    qtbot.waitUntil(lambda: original._central_splitter.height() > 0)
    original._central_splitter.setSizes([210, 390])
    original.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, original._history_dock_widget)
    service.save_window_geometry(original.saveGeometry().data())
    service.save_window_state(original.saveState().data())
    service.save_splitter_sizes(original._central_splitter.sizes())

    restored = MainWindow(settings_service=service)
    qtbot.addWidget(restored)
    restored.show()
    qtbot.waitUntil(lambda: restored._central_splitter.height() > 0)

    assert (
        restored.dockWidgetArea(restored._history_dock_widget)
        is Qt.DockWidgetArea.BottomDockWidgetArea
    )
    original_sizes = original._central_splitter.sizes()
    restored_sizes = restored._central_splitter.sizes()
    # Qt constrains restored width to dock minimum widths offscreen, but the persisted geometry
    # still restores the requested window height alongside the dock/splitter state.
    assert restored.height() == original.height()
    assert restored_sizes[0] / sum(restored_sizes) == pytest.approx(
        original_sizes[0] / sum(original_sizes), abs=0.001
    )


def test_main_window_without_stored_settings_has_a_sane_default_layout(
    tmp_path: Path, qtbot
) -> None:
    window = MainWindow(settings_service=_configure_qsettings_path(tmp_path / "first-run"))
    qtbot.addWidget(window)
    window.resize(800, 600)
    window.show()
    qtbot.waitUntil(lambda: window._central_splitter.height() > 0)

    assert (
        window.dockWidgetArea(window._history_dock_widget) is Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert len(window._central_splitter.sizes()) == 2
    assert all(size > 0 for size in window._central_splitter.sizes())


def test_reset_layout_restores_and_persists_default_docks_and_splitter(
    tmp_path: Path, qtbot
) -> None:
    service = _configure_qsettings_path(tmp_path / "reset-layout")
    window = MainWindow(settings_service=service)
    qtbot.addWidget(window)
    window.resize(800, 600)
    window.show()
    qtbot.waitUntil(lambda: window._central_splitter.height() > 0)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, window._history_dock_widget)
    window._central_splitter.setSizes([300, 100])

    window.desktop_actions.reset_layout.trigger()

    assert (
        window.dockWidgetArea(window._catalog_dock_widget) is Qt.DockWidgetArea.LeftDockWidgetArea
    )
    assert (
        window.dockWidgetArea(window._history_dock_widget) is Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert service.restore_splitter_sizes() == tuple(window._central_splitter.sizes())
    restored = MainWindow(settings_service=service)
    qtbot.addWidget(restored)
    assert (
        restored.dockWidgetArea(restored._history_dock_widget)
        is Qt.DockWidgetArea.RightDockWidgetArea
    )


def test_clear_history_action_empties_store_and_history_dock(tmp_path: Path, qtbot) -> None:
    history_path = tmp_path / "history.json"
    history = HistoryManager(storage_path=history_path)
    history.add_entry("duckdb", "SELECT to_clear")
    window = MainWindow(history_manager=history)
    qtbot.addWidget(window)
    assert window.history_dock.history_table.topLevelItemCount() == 1

    window.desktop_actions.clear_history.trigger()

    assert history.get_all() == []
    assert window.history_dock.history_table.topLevelItemCount() == 0
    assert json.loads(history_path.read_text()) == []


def test_main_window_action_enabled_states_and_status_bar_during_execution(
    tmp_path: Path, qtbot
) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("id,val\n1,100\n2,200\n")

    window = MainWindow()
    qtbot.addWidget(window)
    window._catalog_service.add_paths((csv_file,))
    window._update_catalog_affordances()
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))
    window.editor.setText("SELECT * FROM data")
    window.editor.selectAll()

    # Initial state
    assert window.desktop_actions.run.isEnabled()
    assert not window.desktop_actions.cancel.isEnabled()

    # Trigger Run with a signal spy for result_ready
    with qtbot.waitSignal(window.query_controller.result_ready, timeout=3000):
        window.desktop_actions.run.trigger()

    # Re-enabled after terminal state
    assert window.desktop_actions.run.isEnabled()
    assert not window.desktop_actions.cancel.isEnabled()

    # Check status bar message formatting §10.3
    msg = window.status_bar.currentMessage()
    assert "DuckDB" in msg
    assert "Succeeded" in msg
    assert "Preview Rows: 2" in msg
    assert "Total Rows: 2" not in msg


def test_main_window_close_waits_for_running_schema_workers(qtbot, tmp_path: Path) -> None:
    csv_file = tmp_path / "fast.csv"
    csv_file.write_text("id\n1\n")

    window = MainWindow()
    qtbot.addWidget(window)
    binding = CatalogBinding(
        entry_id=uuid4(), alias="fast", path=csv_file, source_format=SourceFormat.CSV
    )
    window._queue_schema_work(binding)

    assert len(window._schema_workers) == 1
    window.close()

    assert len(window._schema_workers) == 0


def test_main_window_close_calls_query_controller_shutdown(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    shutdown_called = False

    def spy_shutdown():
        nonlocal shutdown_called
        shutdown_called = True

    monkeypatch.setattr(window.query_controller, "shutdown", spy_shutdown)
    window.close()

    assert shutdown_called is True


def test_main_window_result_grid_integration(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    df = pl.DataFrame({"x": [100, 200], "y": ["alpha", "beta"]})

    req_id = uuid4()
    now = datetime.now(UTC)
    request = ExecutionRequest(
        request_id=req_id,
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT * FROM test",
        executable_sql="SELECT * FROM test",
        catalog=(),
        preview_limit=1000,
        submitted_at=now,
    )

    # 1. Succeeded result
    res_success = QueryResult(
        request_id=req_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=df,
        execution_seconds=0.12,
        preview_row_count=2,
        total_row_count=2,
        truncated=False,
        completed_at=now,
    )
    window._on_query_result_ready(res_success, request)

    grid = window.result_table_view
    assert grid.proxy_model().rowCount() == 2
    assert grid.proxy_model().columnCount() == 2
    assert grid.proxy_model().data(grid.proxy_model().index(0, 0), Qt.ItemDataRole.UserRole) == 100
    assert (
        grid.proxy_model().data(grid.proxy_model().index(1, 1), Qt.ItemDataRole.UserRole) == "beta"
    )
    assert "Preview Rows: 2" in window.status_bar.currentMessage()

    # 2. Failed result: grid cleared, error message shown
    res_failed = QueryResult(
        request_id=req_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.05,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=now,
        error_type="SyntaxError",
        error_message="near SELECT",
    )
    window._on_query_result_ready(res_failed, request)
    assert grid.proxy_model().rowCount() == 0
    msg, severity = window.messages_panel.message_at(0)
    assert "Error (SyntaxError): near SELECT" in msg
    assert severity == "error"

    # 3. Cancelled result: grid cleared
    res_cancelled = QueryResult(
        request_id=req_id,
        status=ExecutionStatus.CANCELLED,
        frame=None,
        execution_seconds=0.01,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=now,
    )
    window._on_query_result_ready(res_cancelled, request)
    assert grid.proxy_model().rowCount() == 0
    msg, severity = window.messages_panel.message_at(0)
    assert "cancelled" in msg.lower()
    assert severity == "warning"


def test_main_window_apply_order_to_query(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.editor.setText("SELECT * FROM users")

    executed_sqls: list[str] = []

    def mock_submit(request):
        executed_sqls.append(request.original_sql)
        return True

    monkeypatch.setattr(window.query_controller, "execute", mock_submit)

    # 1. No result present: apply order should be disabled/no-op
    window._on_apply_query_order("id", "ASC")
    assert len(executed_sqls) == 0

    # 2. Result present: apply order updates editor text and submits exactly 1 new execution
    df = pl.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    window.result_table_view.set_frame(df)

    window._on_apply_query_order("id", "ASC")
    assert window.editor.text() == "SELECT * FROM users ORDER BY id ASC"
    assert len(executed_sqls) == 1
    assert executed_sqls[0] == "SELECT * FROM users ORDER BY id ASC"


def test_main_window_query_result_details_and_metrics(qtbot) -> None:
    from datetime import datetime
    from uuid import uuid4

    from wherewolf.domain import EngineKind, ExecutionRequest, ExecutionStatus, QueryResult

    window = MainWindow()
    qtbot.addWidget(window)

    req = ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.SPARK,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=1000,
        submitted_at=datetime.now(UTC),
    )

    # 1. Success result
    df = pl.DataFrame({"x": [1, 2, 3]})
    res_success = QueryResult(
        request_id=req.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=df,
        execution_seconds=0.42,
        preview_row_count=3,
        total_row_count=3,
        truncated=False,
        completed_at=datetime.now(UTC),
    )
    window._on_query_result_ready(res_success, req)
    status_bar = window.statusBar()
    assert status_bar is not None
    assert "spark" in status_bar.currentMessage().lower()
    assert "0.42s" in status_bar.currentMessage()
    assert "3" in status_bar.currentMessage()

    truncated = QueryResult(
        request_id=req.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=df,
        execution_seconds=0.42,
        preview_row_count=3,
        total_row_count=None,
        truncated=True,
        completed_at=datetime.now(UTC),
    )
    window._on_query_result_ready(truncated, req)
    assert "truncated" in status_bar.currentMessage().lower()

    # 2. Failed result
    res_failed = QueryResult(
        request_id=req.request_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.15,
        preview_row_count=0,
        total_row_count=0,
        truncated=False,
        error_type="ExecutionError",
        error_message="Table not found",
        completed_at=datetime.now(UTC),
    )
    window._on_query_result_ready(res_failed, req)
    assert "spark" in status_bar.currentMessage().lower()
    assert "0.15s" in status_bar.currentMessage()
    assert "Table not found" in status_bar.currentMessage()


def test_main_window_result_grid_gui_thread_population(qtbot, monkeypatch) -> None:
    from PyQt6.QtCore import QThread

    window = MainWindow()
    qtbot.addWidget(window)

    app = QCoreApplication.instance()
    assert app is not None
    gui_thread = app.thread()
    assert window.thread() == gui_thread
    assert window.result_table_view.thread() == gui_thread
    assert window.result_table_view.source_model().thread() == gui_thread
    assert window.result_table_view.proxy_model().thread() == gui_thread

    # QueryController.result_ready is connected to _on_query_result_ready
    # Verify execution updates model on GUI thread
    populated_thread: QThread | None = None

    def spy_set_frame(frame):
        nonlocal populated_thread
        populated_thread = QThread.currentThread()
        type(window.result_table_view).set_frame(window.result_table_view, frame)

    monkeypatch.setattr(window.result_table_view, "set_frame", spy_set_frame)

    now = datetime.now(UTC)
    request = ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=1000,
        submitted_at=now,
    )
    result = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"a": [1]}),
        execution_seconds=0.01,
        preview_row_count=1,
        total_row_count=1,
        truncated=False,
        completed_at=now,
    )

    window._on_query_result_ready(result, request)
    assert populated_thread == gui_thread
