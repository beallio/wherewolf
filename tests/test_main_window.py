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


def test_main_window_action_enabled_states_and_status_bar_during_execution(
    tmp_path: Path, qtbot
) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("id,val\n1,100\n2,200\n")

    window = MainWindow()
    qtbot.addWidget(window)
    window._catalog_service.add_paths((csv_file,))
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
