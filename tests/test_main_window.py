from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl
from PyQt6.QtCore import QCoreApplication, QSettings, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
)

from wherewolf.desktop.main_window import MainWindow
from wherewolf.domain import (
    CatalogBinding,
    EngineKind,
    ExecutionRequest,
    ExecutionStatus,
    QueryResult,
    SourceFormat,
)
from wherewolf.services import SettingsService


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

    for dock in window.findChildren(QDockWidget):
        assert dock.objectName()

    menu_titles = [action.text() for action in menu_bar.actions()]
    assert menu_titles == ["File", "Edit", "Query", "View", "Help"]


def test_main_window_query_actions_initial_state_and_shared_instances(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    run_action = window.desktop_actions.run
    cancel_action = window.desktop_actions.cancel
    format_action = window.desktop_actions.format_sql

    assert run_action.isEnabled()
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

    window.desktop_actions.run.trigger()

    assert window.query_controller.status.name == "IDLE"
    assert (
        "No SQL statement to run" in window.status_bar.currentMessage()
        or "empty" in window.status_bar.currentMessage().lower()
        or "statement" in window.status_bar.currentMessage().lower()
    )


def test_main_window_action_enabled_states_and_status_bar_during_execution(
    tmp_path: Path, qtbot
) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("id,val\n1,100\n2,200\n")

    window = MainWindow()
    qtbot.addWidget(window)
    window._catalog_service.add_paths((csv_file,))
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

    worker = window._schema_workers[0]
    with qtbot.waitSignal(worker.result_ready, timeout=3000):
        pass

    assert len(window._schema_workers) == 1
    window.close()

    assert len(window._schema_workers) == 0


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
    assert "Error (SyntaxError): near SELECT" in window._results_text.toPlainText()

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
    assert "cancelled" in window._results_text.toPlainText().lower()
