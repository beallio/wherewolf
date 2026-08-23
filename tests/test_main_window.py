import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import polars as pl
import pytest
from PyQt6.QtCore import (
    QCoreApplication,
    QItemSelection,
    QItemSelectionModel,
    QMimeData,
    QPointF,
    QSettings,
    Qt,
    QThread,
    QUrl,
)
from PyQt6.QtGui import QDropEvent, QFontMetrics, QKeySequence, QStandardItemModel
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from wherewolf.desktop import main_window
from wherewolf.desktop.dialogs import FakeFileDialogService
from wherewolf.desktop.main_window import MainWindow
from wherewolf.desktop.widgets import SqlEditor
from wherewolf.desktop.workers.schema_worker import SchemaWorker
from wherewolf.domain import (
    CatalogBinding,
    CatalogEntry,
    ColumnProfile,
    ColumnSchema,
    EngineKind,
    ExecutionRequest,
    ExecutionStatus,
    ProfileResult,
    QueryResult,
    SchemaResult,
    SourceFormat,
)
from wherewolf.services import (
    CatalogService,
    ExportFormat,
    SettingsService,
    serialise_history_records_to_sql,
)
from wherewolf.storage import HistoryManager, SavedQueryStore
from wherewolf.storage.catalog import CatalogStore


class _ProfileAdapter:
    def __init__(self, responses: list[ProfileResult], delay: float = 0.0) -> None:
        self._responses = responses
        self._delay = delay

    def profile_dataset(self, _entry) -> ProfileResult:
        time.sleep(self._delay)
        if not self._responses:
            raise RuntimeError("no profile response configured")
        return self._responses.pop(0)

    def close(self) -> None:
        pass


class _ProfileRegistry:
    def __init__(self, responses: list[ProfileResult], delay: float = 0.0) -> None:
        self.adapter = _ProfileAdapter(responses=responses, delay=delay)
        self.calls: list[tuple[EngineKind, object]] = []

    def create(self, kind: EngineKind, request_id) -> _ProfileAdapter:
        self.calls.append((kind, request_id))
        return self.adapter


def _write_large_profile_dataset(path: Path, row_count: int, label_width: int = 36) -> int:
    payload = "x" * label_width
    with path.open("w", encoding="utf-8") as handle:
        handle.write("id,name\n")
        for index in range(row_count):
            handle.write(f"{index},row-{index}-{payload}\n")
    return path.stat().st_size


def _configure_qsettings_path(tmp_path: Path) -> SettingsService:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    settings = QSettings(SettingsService.ORGANIZATION, SettingsService.APPLICATION)
    settings.clear()
    return SettingsService(settings)


def test_main_window_restores_catalog_and_persists_catalog_changes(tmp_path: Path, qtbot) -> None:
    available_path = tmp_path / "available.csv"
    available_path.write_text("id\n1")
    missing_path = tmp_path / "missing.csv"
    added_path = tmp_path / "added.csv"
    added_path.write_text("id\n2")
    store = CatalogStore(tmp_path / "catalog.json")
    store.save(
        (
            CatalogEntry(uuid4(), "available", available_path, SourceFormat.CSV),
            CatalogEntry(uuid4(), "missing", missing_path, SourceFormat.CSV),
        )
    )

    window = MainWindow(catalog_store=store)
    qtbot.addWidget(window)

    restored = window._catalog_service.entries
    assert [entry.alias for entry in restored] == ["available", "missing"]
    assert [entry.unavailable for entry in restored] == [False, True]

    window.catalog.add_paths((added_path,))

    assert [entry.alias for entry in store.load()] == ["available", "missing", "added"]


def test_main_window_catalog_persistence_round_trip_between_windows(tmp_path: Path, qtbot) -> None:
    dataset = tmp_path / "persisted.csv"
    dataset.write_text("id\n1", encoding="utf-8")
    store = CatalogStore(tmp_path / "catalog.json")
    settings = _configure_qsettings_path(tmp_path)
    history_manager = HistoryManager(tmp_path / "history.json")
    first = MainWindow(
        catalog_store=store,
        history_manager=history_manager,
        settings_service=settings,
    )
    qtbot.addWidget(first)

    first.catalog.add_paths((dataset,))
    first.close()

    second = MainWindow(
        catalog_store=store,
        history_manager=history_manager,
        settings_service=settings,
    )
    qtbot.addWidget(second)

    assert [entry.path for entry in second._catalog_service.entries] == [dataset]


def test_catalog_persistence_ignores_derived_schema_updates(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    dataset = tmp_path / "available.csv"
    dataset.write_text("id\n1")
    entry = CatalogEntry(uuid4(), "available", dataset, SourceFormat.CSV)
    store = CatalogStore(tmp_path / "catalog.json")
    store.save((entry,))
    writes: list[tuple[CatalogEntry, ...]] = []
    monkeypatch.setattr(store, "save", lambda entries: writes.append(entries))
    window = MainWindow(catalog_store=store)
    qtbot.addWidget(window)

    restored = window._catalog_service.entries[0]
    window._catalog_service.update_schema(SchemaResult(restored.id, ()))

    assert writes == []

    window._catalog_service.rename(restored.id, "renamed")

    assert [entry.alias for entry in writes[-1]] == ["renamed"]


def test_main_window_reinspects_only_available_restored_catalog_entries(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    available_paths = (tmp_path / "one.csv", tmp_path / "two.csv")
    for path in available_paths:
        path.write_text("id\n1")
    missing_path = tmp_path / "missing.csv"
    store = CatalogStore(tmp_path / "catalog.json")
    store.save(
        tuple(
            CatalogEntry(uuid4(), path.stem, path, SourceFormat.CSV)
            for path in (*available_paths, missing_path)
        )
    )
    requested: list[CatalogBinding] = []
    monkeypatch.setattr(
        MainWindow,
        "_queue_schema_work",
        lambda _self, binding: requested.append(binding),
    )
    monkeypatch.setattr(MainWindow, "_queue_profile_work", lambda _self, _binding: None)

    window = MainWindow(catalog_store=store)
    qtbot.addWidget(window)

    assert [binding.path for binding in requested] == list(available_paths)


def test_main_window_restores_editor_draft_without_clobbering_it(tmp_path: Path, qtbot) -> None:
    settings = _configure_qsettings_path(tmp_path)
    first = MainWindow(settings_service=settings)
    qtbot.addWidget(first)
    first.editor.setText("SELECT preserved_draft")
    first.close()

    dataset = tmp_path / "data.csv"
    dataset.write_text("id\n1")
    second = MainWindow(settings_service=settings)
    qtbot.addWidget(second)
    second.catalog.add_paths((dataset,))

    assert second.editor.text() == "SELECT preserved_draft"


def test_main_window_open_and_save_sql_tracks_the_current_file_and_dirty_state(
    tmp_path: Path, qtbot
) -> None:
    opened_path = tmp_path / "opened.sql"
    opened_path.write_text("SELECT opened", encoding="utf-8")
    save_as_path = tmp_path / "saved_copy"
    file_service = FakeFileDialogService((), sql_open_path=opened_path, sql_save_path=save_as_path)
    window = MainWindow(file_dialog_service=file_service)
    qtbot.addWidget(window)

    window.desktop_actions.open_sql.trigger()

    assert window.editor.text() == "SELECT opened"
    assert opened_path.name in window.windowTitle()
    assert not window.isWindowModified()

    window.editor.setText("SELECT changed")

    assert window.isWindowModified()
    assert window.windowTitle().endswith(f"{opened_path.name} *")

    window.desktop_actions.save_sql.trigger()

    assert opened_path.read_text(encoding="utf-8") == "SELECT changed"
    assert not window.isWindowModified()

    window.desktop_actions.save_sql_as.trigger()

    assert save_as_path.with_suffix(".sql").read_text(encoding="utf-8") == "SELECT changed"
    assert save_as_path.with_suffix(".sql").name in window.windowTitle()


def test_open_sql_preserves_a_nonpristine_current_buffer_in_a_separate_tab(
    tmp_path: Path, qtbot
) -> None:
    opened_path = tmp_path / "opened.sql"
    opened_path.write_text("SELECT opened", encoding="utf-8")
    window = MainWindow(file_dialog_service=FakeFileDialogService((), sql_open_path=opened_path))
    qtbot.addWidget(window)
    window.editor.setText("SELECT unsaved")

    window.desktop_actions.open_sql.trigger()

    assert window.editor_tabs.count() == 2
    first = window.editor_tabs.widget(0)
    assert isinstance(first, SqlEditor)
    assert first.text() == "SELECT unsaved"
    assert window.editor.text() == "SELECT opened"


def test_restored_file_backed_draft_uses_disk_text_as_dirty_baseline(tmp_path: Path, qtbot) -> None:
    path = tmp_path / "saved.sql"
    path.write_text("SELECT disk", encoding="utf-8")
    settings = _configure_qsettings_path(tmp_path / "restore-dirty")
    settings.save_editor_tabs((("SELECT draft", path),), active_index=0)

    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)

    assert window.editor.text() == "SELECT draft"
    assert window.isWindowModified()


def test_main_window_save_sql_without_a_current_file_uses_save_as(tmp_path: Path, qtbot) -> None:
    destination = tmp_path / "untitled_query"
    window = MainWindow(file_dialog_service=FakeFileDialogService((), sql_save_path=destination))
    qtbot.addWidget(window)
    window.editor.setText("SELECT untitled")

    window.desktop_actions.save_sql.trigger()

    expected_path = destination.with_suffix(".sql")
    assert expected_path.read_text(encoding="utf-8") == "SELECT untitled"
    assert window._current_sql_path == expected_path


def test_main_window_editor_tabs_create_focus_close_and_preserve_buffers(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.editor_tabs.count() == 1
    assert window.editor_tabs.tabsClosable()
    assert window.editor_tabs.isMovable()
    first_editor = window.current_editor
    assert first_editor is not None
    first_editor.setText("SELECT first_tab")
    assert window.editor_tabs.tabText(0) == "SELECT first_tab"

    assert window.desktop_actions.new_tab.shortcut() == QKeySequence("Ctrl+T")
    window.desktop_actions.new_tab.trigger()

    assert window.editor_tabs.count() == 2
    assert window.editor_tabs.currentIndex() == 1
    second_editor = window.current_editor
    assert second_editor is not None
    assert second_editor is not first_editor
    second_editor.setText("SELECT second_tab")
    assert window.editor_tabs.tabText(1) == "SELECT second_tab"

    window.editor_tabs.setCurrentIndex(0)
    assert window.current_editor is first_editor
    assert window.current_editor.text() == "SELECT first_tab"

    window.editor_tabs.setCurrentIndex(1)
    assert window.current_editor is second_editor
    assert window.current_editor.text() == "SELECT second_tab"

    window.editor_tabs.tabCloseRequested.emit(1)
    assert window.editor_tabs.count() == 1

    window.editor_tabs.tabCloseRequested.emit(0)
    assert window.editor_tabs.count() == 1
    assert window.current_editor is not None
    assert window.current_editor.text() == ""


def test_main_window_editor_tabs_save_each_current_tab_to_its_own_path(
    tmp_path: Path, qtbot
) -> None:
    first_path = tmp_path / "first.sql"
    second_path = tmp_path / "second.sql"
    window = MainWindow()
    qtbot.addWidget(window)

    first_editor = window.current_editor
    assert first_editor is not None
    first_editor.setText("SELECT first")
    window._current_sql_path = first_path
    window._last_saved_sql_text = first_editor.text()

    window.desktop_actions.new_tab.trigger()
    second_editor = window.current_editor
    assert second_editor is not None
    second_editor.setText("SELECT second")
    window._current_sql_path = second_path
    window.desktop_actions.save_sql.trigger()

    assert second_path.read_text(encoding="utf-8") == "SELECT second"

    window.editor_tabs.setCurrentIndex(0)
    window.desktop_actions.save_sql.trigger()

    assert first_path.read_text(encoding="utf-8") == "SELECT first"


def test_main_window_tab_results_restore_without_cross_tab_leaks(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller,
        "execute",
        lambda request: submitted.append(request) or True,
    )

    first_editor = window.current_editor
    assert first_editor is not None
    first_editor.setText("SELECT 1")
    window._on_run_triggered()
    first_request = submitted.pop()
    first_result = QueryResult(
        request_id=first_request.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"tab": ["first"]}),
        execution_seconds=0.01,
        preview_row_count=1,
        total_row_count=1,
        truncated=False,
        completed_at=datetime.now(UTC),
    )

    window.desktop_actions.new_tab.trigger()
    second_editor = window.current_editor
    assert second_editor is not None
    assert not window.result_table_view.has_result()

    window._on_query_result_ready(first_result, first_request)

    assert not window.result_table_view.has_result()

    second_editor.setText("SELECT 2")
    window._on_run_triggered()
    second_request = submitted.pop()
    second_result = QueryResult(
        request_id=second_request.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"tab": ["second"]}),
        execution_seconds=0.01,
        preview_row_count=1,
        total_row_count=1,
        truncated=False,
        completed_at=datetime.now(UTC),
    )
    window._on_query_result_ready(second_result, second_request)

    assert window.result_table_view.frame().to_dicts() == [{"tab": "second"}]

    window.editor_tabs.setCurrentIndex(0)

    assert window.result_table_view.frame().to_dicts() == [{"tab": "first"}]


def test_main_window_restores_editor_tabs_with_paths_and_active_index(
    tmp_path: Path, qtbot
) -> None:
    settings = _configure_qsettings_path(tmp_path / "tab-workspace")
    first_path = tmp_path / "first.sql"
    third_path = tmp_path / "third.sql"
    first = MainWindow(settings_service=settings)
    qtbot.addWidget(first)

    first_editor = first.current_editor
    assert first_editor is not None
    first_editor.setText("SELECT first")
    first._current_sql_path = first_path
    first._last_saved_sql_text = first_editor.text()

    first.desktop_actions.new_tab.trigger()
    second_editor = first.current_editor
    assert second_editor is not None
    second_editor.setText("SELECT second")

    first.desktop_actions.new_tab.trigger()
    third_editor = first.current_editor
    assert third_editor is not None
    third_editor.setText("SELECT third")
    first._current_sql_path = third_path
    first._last_saved_sql_text = third_editor.text()

    first.editor_tabs.setCurrentIndex(1)
    first.close()

    restored = MainWindow(settings_service=settings)
    qtbot.addWidget(restored)

    assert restored.editor_tabs.count() == 3
    restored_editors = [restored.editor_tabs.widget(index) for index in range(3)]
    assert all(isinstance(editor, SqlEditor) for editor in restored_editors)
    typed_editors = [cast(SqlEditor, editor) for editor in restored_editors]
    assert [editor.text() for editor in typed_editors] == [
        "SELECT first",
        "SELECT second",
        "SELECT third",
    ]
    assert restored.editor_tabs.currentIndex() == 1
    assert restored._editor_states[typed_editors[0]].path == first_path
    assert restored._editor_states[typed_editors[1]].path is None
    assert restored._editor_states[typed_editors[2]].path == third_path


def test_main_window_migrates_legacy_single_editor_draft_to_one_tab(tmp_path: Path, qtbot) -> None:
    settings = _configure_qsettings_path(tmp_path / "legacy-draft")
    settings.save_editor_text("SELECT legacy_draft")

    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)

    assert window.editor_tabs.count() == 1
    assert window.current_editor is not None
    assert window.current_editor.text() == "SELECT legacy_draft"


def test_main_window_saves_and_runs_saved_queries(tmp_path: Path, qtbot, monkeypatch) -> None:
    store = SavedQueryStore(tmp_path / "saved_queries.json")
    window = MainWindow(saved_query_store=store)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    monkeypatch.setattr(
        main_window.QInputDialog, "getText", lambda *_args, **_kwargs: ("Daily", True)
    )
    editor = window.current_editor
    assert editor is not None
    editor.setText("SELECT 1")

    window.desktop_actions.save_current_query.trigger()

    assert [query.name for query in store.get_all()] == ["Daily"]
    assert window.saved_queries_dock.query_list.count() == 1

    window._run_saved_query(store.get_all()[0])

    assert submitted[0].executable_sql == "SELECT 1"
    assert submitted[0].parameters == ()


def test_main_window_binds_saved_query_parameters_before_execution(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    store = SavedQueryStore(tmp_path / "saved_queries.json")
    query = store.save_query(
        name="Find user",
        description="",
        sql="SELECT :name, ':name', value::int",
    )
    window = MainWindow(saved_query_store=store)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    monkeypatch.setattr(
        main_window.QInputDialog,
        "getText",
        lambda *_args, **_kwargs: ("'; DROP TABLE t; --", True),
    )

    window._run_saved_query(query)

    assert submitted[0].original_sql == "SELECT :name, ':name', value::int"
    assert submitted[0].executable_sql == "SELECT ?, ':name', value::int"
    assert submitted[0].parameters == ("'; DROP TABLE t; --",)


def test_saved_query_history_keeps_named_parameters_and_rebinds_on_restore(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    store = SavedQueryStore(tmp_path / "saved_queries.json")
    history = HistoryManager(tmp_path / "history.json")
    query = store.save_query(name="Find user", description="", sql="SELECT :name AS name")
    window = MainWindow(saved_query_store=store, history_manager=history)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    monkeypatch.setattr(
        main_window.QInputDialog, "getText", lambda *_args, **_kwargs: ("not persisted", True)
    )

    window._run_saved_query(query)
    request = submitted[0]
    window._on_query_result_ready(
        QueryResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCEEDED,
            frame=pl.DataFrame({"name": ["not persisted"]}),
            execution_seconds=0.01,
            preview_row_count=1,
            total_row_count=1,
            truncated=False,
            completed_at=datetime.now(UTC),
        ),
        request,
    )

    record = history.get_all()[0]
    assert record["query"] == "SELECT :name AS name"
    assert "not persisted" not in (tmp_path / "history.json").read_text(encoding="utf-8")

    window.history_dock.record_selected.emit(record)
    window._on_run_triggered()

    assert submitted[1].original_sql == "SELECT :name AS name"
    assert submitted[1].executable_sql == "SELECT ? AS name"
    assert submitted[1].parameters == ("not persisted",)


def test_main_window_binds_saved_query_dataset_alias_as_a_quoted_identifier(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    dataset = tmp_path / "weekly.csv"
    dataset.write_text("id\n1\n", encoding="utf-8")
    catalog = CatalogService((CatalogEntry(uuid4(), "weekly export", dataset, SourceFormat.CSV),))
    store = SavedQueryStore(tmp_path / "saved_queries.json")
    query = store.save_query(
        name="Weekly rule",
        description="",
        sql="SELECT * FROM {dataset}",
    )
    window = MainWindow(catalog_service=catalog, saved_query_store=store)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    prompted_aliases: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    monkeypatch.setattr(
        main_window.QInputDialog,
        "getItem",
        lambda _parent, _title, _label, aliases, *_args: (
            prompted_aliases.append(tuple(aliases)) or "weekly export",
            True,
        ),
    )

    window._run_saved_query(query)

    assert prompted_aliases == [("weekly export",)]
    assert submitted[0].executable_sql == 'SELECT * FROM "weekly export"'


def test_saved_query_dataset_text_inside_literals_or_comments_never_prompts(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    store = SavedQueryStore(tmp_path / "saved_queries.json")
    query = store.save_query(
        name="Literal token",
        description="",
        sql="SELECT '{dataset}', \"{dataset}\" -- {dataset}\n/* {dataset} */",
    )
    window = MainWindow(saved_query_store=store)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    monkeypatch.setattr(
        main_window.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dataset picker opened")),
    )

    window._run_saved_query(query)

    assert submitted[0].original_sql == query.sql
    assert submitted[0].executable_sql == query.sql


def test_direct_saved_query_result_cannot_apply_order_to_unrelated_editor(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    store = SavedQueryStore(tmp_path / "saved_queries.json")
    query = store.save_query(name="Direct", description="", sql="SELECT 1 AS direct_value")
    window = MainWindow(saved_query_store=store)
    qtbot.addWidget(window)
    window.editor.setText("SELECT unrelated")
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )

    window._run_saved_query(query)
    request = submitted[0]
    window._on_query_result_ready(
        QueryResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCEEDED,
            frame=pl.DataFrame({"direct_value": [1]}),
            execution_seconds=0.01,
            preview_row_count=1,
            total_row_count=1,
            truncated=False,
            completed_at=datetime.now(UTC),
        ),
        request,
    )

    window._on_apply_query_order("direct_value", "ASC")

    assert window.editor.text() == "SELECT unrelated"
    assert "open and run" in window.status_bar.currentMessage().lower()


def test_successful_result_for_a_closed_editor_still_reaches_history(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    history = HistoryManager(tmp_path / "history.json")
    window = MainWindow(history_manager=history)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    window.editor.setText("SELECT closed_tab")
    window._on_run_triggered()
    request = submitted[0]
    window._close_current_editor_tab()

    window._on_query_result_ready(
        QueryResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCEEDED,
            frame=pl.DataFrame({"value": [1]}),
            execution_seconds=0.01,
            preview_row_count=1,
            total_row_count=1,
            truncated=False,
            completed_at=datetime.now(UTC),
        ),
        request,
    )

    assert [record["query"] for record in history.get_all()] == ["SELECT closed_tab"]


def test_direct_saved_query_result_stays_with_launch_tab_and_cannot_be_ordered(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    store = SavedQueryStore(tmp_path / "saved_queries.json")
    query = store.save_query(name="Direct", description="", sql="SELECT 1 AS direct_value")
    window = MainWindow(saved_query_store=store)
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )

    first = window.editor
    first.setText("SELECT first_tab_sql")
    window._run_saved_query(query)
    request = submitted[0]

    second = window._new_editor_tab()
    second.setText("SELECT second_tab_sql")
    window._on_query_result_ready(
        QueryResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCEEDED,
            frame=pl.DataFrame({"direct_value": [1]}),
            execution_seconds=0.01,
            preview_row_count=1,
            total_row_count=1,
            truncated=False,
            completed_at=datetime.now(UTC),
        ),
        request,
    )

    assert not window.result_table_view.has_result()
    assert second.text() == "SELECT second_tab_sql"

    window.editor_tabs.setCurrentIndex(window.editor_tabs.indexOf(first))

    assert window.result_table_view.frame().to_dicts() == [{"direct_value": 1}]
    window._on_apply_query_order("direct_value", "ASC")
    assert first.text() == "SELECT first_tab_sql"
    assert "open and run" in window.status_bar.currentMessage().lower()


def test_catalog_persistence_failure_remains_visible_until_retry_succeeds(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    dataset = tmp_path / "orders.csv"
    dataset.write_text("id\n1\n", encoding="utf-8")
    store = CatalogStore(tmp_path / "catalog.json")
    saved_projections: list[tuple[CatalogEntry, ...]] = []
    original_save = store.save

    def fail_once(entries: tuple[CatalogEntry, ...]) -> None:
        saved_projections.append(entries)
        if len(saved_projections) == 1:
            raise OSError("disk full")
        original_save(entries)

    monkeypatch.setattr(store, "save", fail_once)
    window = MainWindow(catalog_store=store)
    qtbot.addWidget(window)

    window.catalog.add_paths((dataset,))

    assert window.catalog.model.rowCount() == 1
    assert store.load() == ()
    assert "Could not save dataset catalog" in window.status_bar.currentMessage()
    assert window._last_persisted_catalog == ()

    entry = window._catalog_service.entries[0]
    window._catalog_service.rename(entry.id, "renamed_orders")

    assert [entry.alias for entry in store.load()] == ["renamed_orders"]
    assert window._last_persisted_catalog == window._catalog_projection()


def test_refresh_catalog_schema_rechecks_returned_and_missing_files(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    returned_path = tmp_path / "returned.csv"
    returned_service = CatalogService()
    returned = returned_service.add_paths((returned_path,)).added[0]
    returned_service.refresh_availability(returned.id)
    returned_window = MainWindow(catalog_service=returned_service)
    qtbot.addWidget(returned_window)
    returned_schema: list[CatalogBinding] = []
    returned_profiles: list[CatalogBinding] = []
    monkeypatch.setattr(returned_window, "_queue_schema_work", returned_schema.append)
    monkeypatch.setattr(returned_window, "_queue_profile_work", returned_profiles.append)

    returned_path.write_text("id\n1\n", encoding="utf-8")
    returned_window._on_refresh_catalog_schema(
        CatalogBinding(returned.id, returned.alias, returned.path, returned.source_format)
    )

    assert returned_window._catalog_service.entries[0].unavailable is False
    assert [binding.entry_id for binding in returned_schema] == [returned.id]
    assert [binding.entry_id for binding in returned_profiles] == [returned.id]

    missing_path = tmp_path / "missing.csv"
    missing_path.write_text("id\n1\n", encoding="utf-8")
    missing_service = CatalogService()
    missing = missing_service.add_paths((missing_path,)).added[0]
    missing_window = MainWindow(catalog_service=missing_service)
    qtbot.addWidget(missing_window)
    missing_schema: list[CatalogBinding] = []
    missing_profiles: list[CatalogBinding] = []
    monkeypatch.setattr(missing_window, "_queue_schema_work", missing_schema.append)
    monkeypatch.setattr(missing_window, "_queue_profile_work", missing_profiles.append)

    missing_path.unlink()
    missing_window._on_refresh_catalog_schema(
        CatalogBinding(missing.id, missing.alias, missing.path, missing.source_format)
    )

    assert missing_window._catalog_service.entries[0].unavailable is True
    assert missing_schema == []
    assert missing_profiles == []


def test_edit_actions_and_find_replace_next_follow_the_active_tab(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    first = window.editor
    first.setText("first target")
    first.setCursorPosition(0, len(first.text()))
    first.insert("!")
    window.find_replace_action.trigger()
    dialog = window.find_replace_dialog

    second = window._new_editor_tab()
    second.setText("second target")
    second.setCursorPosition(0, len(second.text()))
    second.insert("!")

    window.undo_action.trigger()
    assert first.text() == "first target!"
    assert second.text() == "second target"
    window.redo_action.trigger()
    assert first.text() == "first target!"
    assert second.text() == "second target!"

    found_in: list[SqlEditor] = []
    original_find_text = SqlEditor.find_text

    def record_find(editor: SqlEditor, value: str) -> bool:
        found_in.append(editor)
        return original_find_text(editor, value)

    monkeypatch.setattr(SqlEditor, "find_text", record_find)
    dialog.find_input.setText("target")
    dialog.find_next_button.click()
    assert found_in == [second]

    dialog.replace_input.setText("changed")
    dialog.replace_next_button.click()
    assert first.text() == "first target!"
    assert second.text() == "second changed!"


def test_accepted_editor_theme_updates_existing_and_new_tabs(tmp_path: Path, qtbot) -> None:
    settings = _configure_qsettings_path(tmp_path / "accepted-multi-tab-theme")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)
    first = window.editor
    second = window._new_editor_tab()

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    dialog.editor_theme_selector.setCurrentText("Solarized Light")
    dialog.accept()

    third = window._new_editor_tab()

    assert (first.theme_name, second.theme_name, third.theme_name) == (
        "Solarized Light",
        "Solarized Light",
        "Solarized Light",
    )
    assert settings.restore_editor_theme() == "Solarized Light"


def test_open_sql_preserves_clean_file_backed_tab_and_failure_does_not_change_tabs(
    tmp_path: Path, qtbot
) -> None:
    first_path = tmp_path / "first.sql"
    first_path.write_text("SELECT first", encoding="utf-8")
    second_path = tmp_path / "second.sql"
    second_path.write_text("SELECT second", encoding="utf-8")
    invalid_path = tmp_path / "invalid.sql"
    invalid_path.write_bytes(b"\xff")
    window = MainWindow(file_dialog_service=FakeFileDialogService((), sql_open_path=first_path))
    qtbot.addWidget(window)

    window.desktop_actions.open_sql.trigger()
    first = window.editor
    window._file_dialog_service = FakeFileDialogService((), sql_open_path=second_path)
    window.desktop_actions.open_sql.trigger()

    assert window.editor_tabs.count() == 2
    assert first.text() == "SELECT first"
    assert window.editor.text() == "SELECT second"

    window._file_dialog_service = FakeFileDialogService((), sql_open_path=None)
    window.desktop_actions.open_sql.trigger()
    assert window.editor_tabs.count() == 2
    assert window.editor.text() == "SELECT second"

    window._file_dialog_service = FakeFileDialogService((), sql_open_path=invalid_path)
    window.desktop_actions.open_sql.trigger()
    assert window.editor_tabs.count() == 2
    assert window.editor.text() == "SELECT second"


def test_restored_unknown_baseline_is_dirty_and_tab_switch_recomputes_dirty_state(
    tmp_path: Path, qtbot
) -> None:
    clean_path = tmp_path / "clean.sql"
    clean_path.write_text("SELECT clean", encoding="utf-8")
    missing_path = tmp_path / "missing.sql"
    unreadable_path = tmp_path / "unreadable.sql"
    unreadable_path.write_bytes(b"\xff")
    settings = _configure_qsettings_path(tmp_path / "unknown-baseline")
    settings.save_editor_tabs(
        (
            ("SELECT clean", clean_path),
            ("SELECT missing", missing_path),
            ("SELECT preserved", unreadable_path),
        ),
        active_index=0,
    )

    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)

    assert not window.isWindowModified()
    window.editor_tabs.setCurrentIndex(1)
    assert window.editor.text() == "SELECT missing"
    assert window._last_saved_sql_text is None
    assert window.isWindowModified()
    window.editor_tabs.setCurrentIndex(2)
    assert window.editor.text() == "SELECT preserved"
    assert window._last_saved_sql_text is None
    assert window.isWindowModified()
    window.editor_tabs.setCurrentIndex(0)
    assert not window.isWindowModified()


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

    assert len(window.findChildren(QToolBar)) == 2

    for dock in window.findChildren(QDockWidget):
        assert dock.objectName()

    menu_titles = [action.text() for action in menu_bar.actions()]
    assert menu_titles == ["&File", "&Edit", "&Query", "&View", "&Help"]


def test_main_window_result_summary_is_hidden_until_a_query_finishes(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.result_summary_label.objectName() == "result_summary_label"
    assert window.result_summary_label.isHidden()


def test_main_window_top_level_menus_have_distinct_mnemonics(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    menus = (
        window.file_menu,
        window.edit_menu,
        window.query_menu,
        window.view_menu,
        window.help_menu,
    )
    titles = [menu.title() for menu in menus]
    mnemonics = [title[1].lower() for title in titles]

    assert all(title.startswith("&") for title in titles)
    assert len(mnemonics) == len(set(mnemonics))


def test_main_window_file_menu_exposes_add_datasets_and_quit(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    file_actions = window.file_menu.actions()
    assert file_actions[0] is window.desktop_actions.add_datasets
    assert window.quit_action in file_actions
    shortcuts = window.quit_action.shortcuts()
    assert QKeySequence("Ctrl+Q") in shortcuts
    assert any(
        QKeySequence("Ctrl+Q").matches(shortcut) == QKeySequence.SequenceMatch.ExactMatch
        for shortcut in shortcuts
    )
    assert window.desktop_actions.clear_history not in file_actions
    assert window.desktop_actions.clear_history in window.edit_menu.actions()


def test_main_window_quit_action_closes_the_window(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.quit_action.trigger()

    assert not window.isVisible()
    app = QCoreApplication.instance()
    assert app is not None
    app.processEvents()


def test_main_window_view_menu_reopens_a_closed_dock_without_affecting_siblings(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    history = window._history_dock_widget
    sibling = window.catalog_dock
    assert history.isVisible()
    assert sibling.isVisible()

    history.close()
    assert not history.isVisible()
    assert sibling.isVisible()

    history_action = next(
        (action for action in window.view_menu.actions() if action.text() == "History"), None
    )
    assert history_action is not None
    history_action.trigger()

    assert history.isVisible()
    assert sibling.isVisible()


def test_main_window_query_controls_are_visible_without_a_scroll_area_at_normal_widths(
    qtbot,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert not window.main_toolbar.findChildren(QScrollArea)
    window.show()
    for width in (1024, 1280, 1440, 1600):
        window.resize(width, 768)
        qtbot.wait(20)
        for object_name in (
            "engine_selector",
            "input_dialect_selector",
            "preview_limit_selector",
        ):
            control = window.findChild(QWidget, object_name)
            assert control is not None
            assert control.isVisible(), f"{object_name} is hidden at {width}px"


def test_main_window_toolbars_share_one_row_and_remain_movable(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(20)

    assert window.main_toolbar.isMovable()
    assert window.query_controls_toolbar.isMovable()
    assert window.main_toolbar.geometry().y() == window.query_controls_toolbar.geometry().y()


def test_main_window_query_selectors_keep_natural_width_at_wide_size(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1600, 768)
    window.show()
    qtbot.wait(20)

    for selector in (window.engine_selector, window.input_dialect_selector):
        assert abs(selector.width() - selector.sizeHint().width()) <= 8

    assert window.engine_selector.sizeHint().width() < 150


def test_main_window_missing_layout_version_skips_state_restore_and_records_current(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    service = _configure_qsettings_path(tmp_path / "missing-layout-version")
    service.save_window_state(b"old-toolbar-layout")
    restored_states: list[bytes] = []
    monkeypatch.setattr(
        MainWindow,
        "restoreState",
        lambda _window, state: restored_states.append(bytes(state)),
    )

    window = MainWindow(settings_service=service)
    qtbot.addWidget(window)

    assert restored_states == []
    assert service.restore_window_layout_version() == MainWindow.LAYOUT_SCHEMA_VERSION


def test_main_window_current_layout_version_restores_saved_state(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    service = _configure_qsettings_path(tmp_path / "current-layout-version")
    service.save_window_state(b"current-toolbar-layout")
    service.save_window_layout_version(MainWindow.LAYOUT_SCHEMA_VERSION)
    restored_states: list[bytes] = []
    monkeypatch.setattr(
        MainWindow,
        "restoreState",
        lambda _window, state: restored_states.append(bytes(state)),
    )

    window = MainWindow(settings_service=service)
    qtbot.addWidget(window)

    assert restored_states == [b"current-toolbar-layout"]


def test_main_window_stale_layout_version_preserves_unrelated_settings(
    qtbot, tmp_path: Path
) -> None:
    service = _configure_qsettings_path(tmp_path / "stale-layout-version")
    geometry = b"geometry"
    splitter_sizes = (240, 360)
    service.save_window_geometry(geometry)
    service.save_window_state(b"stale-toolbar-layout")
    service.save_splitter_sizes(splitter_sizes)
    service.save_editor_font_size(17)
    service.save_window_layout_version(MainWindow.LAYOUT_SCHEMA_VERSION - 1)

    window = MainWindow(settings_service=service)
    qtbot.addWidget(window)

    assert service.restore_window_geometry() == geometry
    assert service.restore_window_state() == b"stale-toolbar-layout"
    assert service.restore_splitter_sizes() == splitter_sizes
    assert service.restore_editor_font_size() == 17
    assert service.restore_window_layout_version() == MainWindow.LAYOUT_SCHEMA_VERSION


@pytest.mark.parametrize("view_name", ("results", "catalog", "schema", "history"))
def test_all_tabular_views_allow_column_reordering(qtbot, view_name: str) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    headers = {
        "results": window.result_table_view.horizontalHeader(),
        "catalog": window.catalog.view.horizontalHeader(),
        "schema": window.schema_panel._table_widget.horizontalHeader(),
        "history": window.history_dock.history_table.header(),
    }
    header = headers[view_name]
    assert header is not None
    assert header.sectionsMovable(), view_name

    if view_name == "schema":
        header.moveSection(0, 1)
        assert header.visualIndex(0) == 1


def test_preview_limit_input_is_font_sized_and_accepts_maximum_value(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    unconstrained = QLineEdit()
    qtbot.addWidget(unconstrained)

    assert window.preview_limit_selector.maximumWidth() < unconstrained.sizeHint().width()
    expected_text_width = QFontMetrics(window.preview_limit_selector.font()).horizontalAdvance(
        "100000"
    )
    assert window.preview_limit_selector.maximumWidth() >= expected_text_width
    validator = window.preview_limit_selector.validator()
    assert validator is not None
    state, _, _ = validator.validate("100000", 0)
    assert state.name == "Acceptable"


def test_main_window_results_expose_export_controls_and_query_actions_at_1024px(
    qtbot,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.resize(1024, 768)
    qtbot.wait(20)

    for object_name in (
        "preview_filter_input",
        "export_button",
    ):
        control = window.findChild(QWidget, object_name)
        assert control is not None
        assert control.isVisible(), f"{object_name} is hidden at 1024px"

    assert window.findChild(QWidget, "export_format_selector") is None
    assert window.findChild(QWidget, "export_scope_selector") is None

    for object_name in (
        "export_preview_button",
        "export_full_button",
        "export_selection_button",
    ):
        assert window.findChild(QWidget, object_name) is None

    assert all(
        action not in window.main_toolbar.actions()
        for action in (
            window.desktop_actions.export_preview,
            window.desktop_actions.export_full,
            window.desktop_actions.export_selection,
        )
    )
    query_actions = window.query_menu.actions()
    assert window.desktop_actions.export_preview in query_actions
    assert window.desktop_actions.export_full in query_actions
    assert window.desktop_actions.export_selection in query_actions


def test_main_window_export_button_writes_selected_parquet_scope(
    tmp_path: Path, qtbot, monkeypatch
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
    window._on_query_result_ready(replace(result, request_id=request.request_id), request)

    def accept_parquet_preview(dialog: main_window.ExportOptionsDialog) -> int:
        dialog.format_selector.setCurrentIndex(
            dialog.format_selector.findData(ExportFormat.PARQUET)
        )
        dialog.scope_selector.setCurrentIndex(dialog.scope_selector.findData("preview"))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window.ExportOptionsDialog, "exec", accept_parquet_preview)

    with qtbot.waitSignal(window.export_controller.result_ready, timeout=3000):
        window.export_button.click()

    artifact = destination.with_suffix(".parquet")
    assert artifact.exists()
    assert pl.read_parquet(artifact).to_dicts() == [{"id": 1}, {"id": 2}]


def test_export_options_dialog_accepts_chosen_values_and_persists_them(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.export_button.setEnabled(True)
    calls: list[tuple[bool, ExportFormat | None]] = []
    monkeypatch.setattr(
        window,
        "_start_export",
        lambda full_export, export_format=None: calls.append((full_export, export_format)),
    )
    dialogs: list[main_window.ExportOptionsDialog] = []

    def accept_full_excel(dialog: main_window.ExportOptionsDialog) -> int:
        dialogs.append(dialog)
        dialog.format_selector.setCurrentIndex(dialog.format_selector.findData(ExportFormat.XLSX))
        dialog.scope_selector.setCurrentIndex(dialog.scope_selector.findData("full"))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window.ExportOptionsDialog, "exec", accept_full_excel)

    window.export_button.click()

    assert len(dialogs) == 1
    assert calls == [(True, ExportFormat.XLSX)]
    assert window._settings_service.restore_export_format() == ExportFormat.XLSX.value
    assert window._settings_service.restore_export_scope() == "full"

    def cancel(dialog: main_window.ExportOptionsDialog) -> int:
        dialogs.append(dialog)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window.ExportOptionsDialog, "exec", cancel)
    window.export_button.click()

    assert len(dialogs) == 2
    assert dialogs[-1].format_selector.currentData() is ExportFormat.XLSX
    assert dialogs[-1].scope_selector.currentData() == "full"
    assert calls == [(True, ExportFormat.XLSX)]


def test_export_scope_actions_bypass_export_options_dialog(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    for action in (
        window.desktop_actions.export_preview,
        window.desktop_actions.export_full,
        window.desktop_actions.export_selection,
    ):
        action.setEnabled(True)
    window._settings_service.save_export_format(ExportFormat.PARQUET.value)
    starts: list[tuple[bool, ExportFormat | None]] = []
    selections: list[ExportFormat | None] = []
    monkeypatch.setattr(
        window,
        "_start_export",
        lambda full_export, export_format=None: starts.append((full_export, export_format)),
    )
    monkeypatch.setattr(
        window,
        "_export_selection",
        lambda export_format=None: selections.append(export_format),
    )
    monkeypatch.setattr(
        main_window.ExportOptionsDialog,
        "exec",
        lambda _dialog: pytest.fail("scope actions must not open the options dialog"),
    )

    window.desktop_actions.export_preview.trigger()
    window.desktop_actions.export_full.trigger()
    window.desktop_actions.export_selection.trigger()

    assert starts == [(False, ExportFormat.PARQUET), (True, ExportFormat.PARQUET)]
    assert selections == [ExportFormat.PARQUET]


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


def test_help_menu_exposes_sql_dialect_reference_submenu_and_links(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    submenu_action = next(
        action for action in window.help_menu.actions() if action.text() == "SQL Dialect Reference"
    )
    submenu = submenu_action.menu()
    assert isinstance(submenu, QMenu)
    assert [action.text() for action in submenu.actions()] == list(
        main_window.SQL_DIALECT_REFERENCE_URLS
    )
    assert all(
        url.startswith("https://") and url
        for url in main_window.SQL_DIALECT_REFERENCE_URLS.values()
    )

    opened: list[str] = []
    monkeypatch.setattr(main_window.webbrowser, "open", opened.append)
    for label, url in main_window.SQL_DIALECT_REFERENCE_URLS.items():
        next(action for action in submenu.actions() if action.text() == label).trigger()
        assert opened[-1] == url


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
    assert item.text() == "Spark"
    tooltip = item.data(Qt.ItemDataRole.ToolTipRole)
    assert isinstance(tooltip, str)
    assert "wherewolf[spark]" in tooltip
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
        "Clear History",
    ]
    assert actions[:2] == [window.undo_action, window.redo_action]
    assert actions[2:5] == [window.cut_action, window.copy_action, window.paste_action]
    assert window.copy_action is not window.editor.edit_actions[3]
    assert window.select_all_action.shortcut().toString() == "Ctrl+A"
    assert window.find_replace_action.shortcut().toString() == "Ctrl+F"
    assert window.toggle_comment_action.shortcut().toString() == "Ctrl+/"


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


def test_main_window_edit_actions_and_find_replace_follow_the_active_tab(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    first = window.editor
    first.setText("SELECT old_value")
    window.find_replace_action.trigger()
    dialog = window.find_replace_dialog
    second = window._new_editor_tab()
    second.setText("SELECT old_value")

    window.toggle_comment_action.trigger()
    dialog.find_input.setText("old_value")
    dialog.replace_input.setText("new_value")
    dialog.replace_all_button.click()

    assert first.text() == "SELECT old_value"
    assert second.text() == "-- SELECT new_value"


def test_main_window_theme_preview_and_rejection_updates_every_open_tab(
    tmp_path: Path, qtbot
) -> None:
    settings = _configure_qsettings_path(tmp_path / "multi-tab-theme")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)
    first = window.editor
    second = window._new_editor_tab()
    original_themes = (first.theme_name, second.theme_name)

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    dialog.editor_theme_selector.setCurrentText("Light")

    assert (first.theme_name, second.theme_name) == ("Light", "Light")
    dialog.reject()

    assert (first.theme_name, second.theme_name) == original_themes


def test_main_window_preview_filter_reduces_rows_and_clear_restores_them(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.result_table_view.set_frame(pl.DataFrame({"name": ["Ada", "Grace", "Ada Lovelace"]}))

    assert window.result_table_view.proxy_model().rowCount() == 3
    window.preview_filter_input.setText("ada")
    assert window.result_table_view.proxy_model().rowCount() == 2
    window.clear_preview_filter_action.trigger()
    assert window.result_table_view.proxy_model().rowCount() == 3


def test_main_window_preview_filter_supports_sql_predicates_and_nonblocking_errors(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.result_table_view.set_frame(
        pl.DataFrame(
            {
                "age": [25, 41, 55],
                "region": ["West", "East", "East"],
            }
        )
    )

    window.preview_filter_input.setText("age > 40")
    assert window.result_table_view.proxy_model().rowCount() == 2
    assert window.preview_filter_error.isHidden()

    window.preview_filter_input.setText("East")
    assert window.result_table_view.proxy_model().rowCount() == 2
    assert window.preview_filter_error.isHidden()

    window.preview_filter_input.setText("age >")
    assert window.result_table_view.proxy_model().rowCount() == 2
    assert not window.preview_filter_error.isHidden()
    assert "age" in window.preview_filter_error.text()

    window.preview_filter_input.setText("missing_column = 1")
    assert window.result_table_view.proxy_model().rowCount() == 2
    assert "missing_column" in window.preview_filter_error.text()


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


def test_main_window_navigation_activates_exact_duckdb_error_location_in_originating_selection(
    qtbot, monkeypatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    origin = window.editor
    origin.setText("SELECT 1;\n  SELECT\n    missing_column\n  FROM range(3)")
    origin.setSelection(1, 2, 3, len("  FROM range(3)"))

    window._on_run_triggered()
    request = submitted.pop()
    assert request.executable_sql == "SELECT\n    missing_column\n  FROM range(3)"
    result = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.01,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="BinderException",
        error_message=(
            'Binder Error: Referenced column "missing_column" not found!\n\n'
            "LINE 2:     missing_column\n"
            "            ^"
        ),
    )
    window._on_query_result_ready(result, request)
    other = window._new_editor_tab()
    other.setText("SELECT unrelated")
    before_activation = other.getCursorPosition()
    item = window.messages_panel._list_widget.item(0)
    assert item is not None

    window.messages_panel._list_widget.itemActivated.emit(item)

    assert window.current_editor is origin
    assert origin.getCursorPosition() == (2, 4)
    assert other.getCursorPosition() == before_activation


@pytest.mark.parametrize(
    "message",
    (
        "Parser Error: syntax error at end of input",
        "Binder Error\n\nLINE 1: SELECT different_column\n        ^",
    ),
)
def test_main_window_withholds_navigation_when_error_location_is_not_exact(
    qtbot, monkeypatch, message: str
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    window.editor.setText("SELECT missing_column")
    window._on_run_triggered()
    request = submitted.pop()
    cursor_before = window.editor.getCursorPosition()
    window._on_query_result_ready(
        QueryResult(
            request_id=request.request_id,
            status=ExecutionStatus.FAILED,
            frame=None,
            execution_seconds=0.01,
            preview_row_count=0,
            total_row_count=None,
            truncated=False,
            completed_at=datetime.now(UTC),
            error_type="BinderException",
            error_message=message,
        ),
        request,
    )
    item = window.messages_panel._list_widget.item(0)
    assert item is not None

    window.messages_panel._list_widget.itemActivated.emit(item)

    assert window.editor.getCursorPosition() == cursor_before


def test_main_window_rejects_navigation_when_editor_changes_before_result_or_activation(
    qtbot, monkeypatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(
        window.query_controller, "execute", lambda request: submitted.append(request) or True
    )
    editor = window.editor
    editor.setText("SELECT missing_column")
    window._on_run_triggered()
    request = submitted.pop()
    result = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.01,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="BinderException",
        error_message="Binder Error\n\nLINE 1: SELECT missing_column\n               ^",
    )
    editor.setText("SELECT changed_before_result")
    cursor_before_result = editor.getCursorPosition()
    window._on_query_result_ready(result, request)
    item = window.messages_panel._list_widget.item(0)
    assert item is not None
    window.messages_panel._list_widget.itemActivated.emit(item)
    assert editor.getCursorPosition() == cursor_before_result

    editor.setText("SELECT missing_column")
    window._on_run_triggered()
    request = submitted.pop()
    window._on_query_result_ready(replace(result, request_id=request.request_id), request)
    item = window.messages_panel._list_widget.item(0)
    assert item is not None
    editor.setText("SELECT changed_before_activation")
    editor.setCursorPosition(0, 0)
    window.messages_panel._list_widget.itemActivated.emit(item)
    assert editor.getCursorPosition() == (0, 0)


def test_main_window_raises_messages_tab_only_for_failed_query_results(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    results_tabs = window.findChild(QTabWidget, "results_tabs")
    assert results_tabs is not None
    results_page = results_tabs.widget(0)
    assert results_page is not None

    request = ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=100,
        submitted_at=datetime.now(UTC),
    )
    failed = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.01,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="SyntaxError",
        error_message="bad SQL",
    )
    succeeded = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"value": [1]}),
        execution_seconds=0.01,
        preview_row_count=1,
        total_row_count=1,
        truncated=False,
        completed_at=datetime.now(UTC),
    )

    results_tabs.setCurrentWidget(results_page)
    window._on_query_result_ready(failed, request)
    assert results_tabs.currentWidget() is window.messages_panel

    results_tabs.setCurrentWidget(results_page)
    window._on_query_result_ready(succeeded, request)
    assert results_tabs.currentWidget() is results_page

    window.editor._update_status("editor diagnostic")
    assert results_tabs.currentWidget() is results_page


def test_main_window_keeps_a_result_summary_until_the_next_run_starts(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    request = ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=3,
        submitted_at=datetime.now(UTC),
    )
    succeeded = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"value": [1, 2, 3]}),
        execution_seconds=1.25,
        preview_row_count=3,
        total_row_count=5,
        truncated=True,
        completed_at=datetime.now(UTC),
    )
    failed = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.5,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="SyntaxError",
        error_message="bad SQL",
    )
    cancelled = QueryResult(
        request_id=request.request_id,
        status=ExecutionStatus.CANCELLED,
        frame=None,
        execution_seconds=0.75,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
    )

    window._on_query_result_ready(succeeded, request)

    assert not window.result_summary_label.isHidden()
    assert window.result_summary_label.text() == (
        "DuckDB · showing 3 of 5 rows · 1.25s · truncated at 3 preview rows"
    )

    window._on_query_status_changed(ExecutionStatus.RUNNING)

    assert window.result_summary_label.text() == ""
    assert window.result_summary_label.isHidden()

    window._on_query_result_ready(failed, request)
    assert window.result_summary_label.text() == "DuckDB · failed after 0.50s"

    window._on_query_result_ready(cancelled, request)
    assert window.result_summary_label.text() == "DuckDB · cancelled after 0.75s"


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


def test_main_window_preferences_persist_result_auto_size_policy(tmp_path: Path, qtbot) -> None:
    settings = _configure_qsettings_path(tmp_path / "result-auto-size-preferences")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    dialog.auto_size_columns.setChecked(False)
    dialog.auto_size_max_width.setValue(150)
    dialog.accept()

    assert settings.restore_auto_size_columns() is False
    assert settings.restore_auto_size_max_width() == 150

    window.result_table_view.set_frame(pl.DataFrame({"wide": ["x" * 400]}))
    assert window.result_table_view.columnWidth(0) < 150

    restored_window = MainWindow(settings_service=settings)
    qtbot.addWidget(restored_window)
    assert restored_window.result_table_view._auto_size_columns_enabled is False
    assert restored_window.result_table_view._auto_size_max_width == 150


def test_main_window_moves_editor_theme_to_preferences_and_keeps_saved_theme(
    tmp_path: Path, qtbot
) -> None:
    settings = _configure_qsettings_path(tmp_path / "theme-preferences")
    settings.save_editor_theme("Light")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)

    assert window.query_controls_toolbar.findChild(QComboBox, "editor_theme_selector") is None
    assert window.editor.theme_name == "Light"

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    assert dialog.editor_theme_selector.currentText() == "Light"
    dialog.editor_theme_selector.setCurrentText("Dark")
    dialog.accept()

    assert settings.restore_editor_theme() == "Dark"
    assert window.editor.theme_name == "Dark"


def test_main_window_preferences_preview_editor_theme_and_cancel_restores_it(
    tmp_path: Path, qtbot
) -> None:
    settings = _configure_qsettings_path(tmp_path / "theme-preview-cancel")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)
    original_theme = window.editor.theme_name

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    dialog.editor_theme_selector.setCurrentText("Light")
    assert window.editor.theme_name == "Light"

    dialog.reject()

    assert window.editor.theme_name == original_theme
    assert settings.restore_editor_theme() == original_theme


def test_main_window_preferences_preview_editor_theme_and_accept_persists_it(
    tmp_path: Path, qtbot
) -> None:
    settings = _configure_qsettings_path(tmp_path / "theme-preview-accept")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    dialog.editor_theme_selector.setCurrentText("Solarized Light")
    assert window.editor.theme_name == "Solarized Light"
    dialog.accept()

    assert window.editor.theme_name == "Solarized Light"
    assert settings.restore_editor_theme() == "Solarized Light"


def test_main_window_preferences_apply_program_theme_live_and_persist_it(
    tmp_path: Path, qtbot
) -> None:
    from wherewolf.desktop.theming import ThemeMode, build_palette

    settings = _configure_qsettings_path(tmp_path / "program-theme-preferences")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    window.preferences_action.trigger()
    dialog = window.preferences_dialog
    dialog.program_theme_selector.setCurrentText(ThemeMode.DARK.value)

    assert app.palette().color(app.palette().ColorRole.Base) == build_palette(ThemeMode.DARK).color(
        app.palette().ColorRole.Base
    )
    dialog.accept()

    assert settings.restore_program_theme() == ThemeMode.DARK.value


def test_main_window_opens_value_counts_window_for_schema_request(tmp_path: Path, qtbot) -> None:
    from wherewolf.domain import CatalogEntry, ColumnSchema, SourceFormat

    source = tmp_path / "users.csv"
    source.write_text("category\na\n")
    entry = CatalogEntry(
        id=uuid4(),
        alias="users",
        path=source,
        source_format=SourceFormat.CSV,
        schema=(ColumnSchema("category", "VARCHAR"),),
    )
    window = MainWindow()
    qtbot.addWidget(window)

    window.schema_panel.value_counts_requested.emit(entry, "category")
    qtbot.waitUntil(lambda: len(window._value_counts_windows) == 1)

    assert window._value_counts_windows[0].windowTitle() == "Value counts: users.category"


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


def test_main_window_drop_routes_through_add_handler_and_queues_schema_work(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    csv_file = tmp_path / "dropped.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow(catalog_service=CatalogService())
    qtbot.addWidget(window)
    monkeypatch.setattr(window._settings_service, "restore_profile_on_load", lambda: False)
    queued_schema_work: list[CatalogBinding] = []
    monkeypatch.setattr(window, "_queue_schema_work", queued_schema_work.append)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(csv_file))])
    event = QDropEvent(
        QPointF(1.0, 1.0),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.dropEvent(event)

    assert event.isAccepted()
    assert len(queued_schema_work) == 1
    assert "Added `dropped` to catalog." in window.status_bar.currentMessage()


def test_main_window_drop_surfaces_unsupported_source_warning(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    unsupported_file = tmp_path / "unsupported.xls"
    supported_file = tmp_path / "supported.csv"
    unsupported_file.write_text("id\n1\n")
    supported_file.write_text("id\n1\n")
    window = MainWindow(catalog_service=CatalogService())
    qtbot.addWidget(window)
    monkeypatch.setattr(window._settings_service, "restore_profile_on_load", lambda: False)
    monkeypatch.setattr(window, "_queue_schema_work", lambda _binding: None)
    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile(str(unsupported_file)),
            QUrl.fromLocalFile(str(supported_file)),
        ]
    )
    event = QDropEvent(
        QPointF(1.0, 1.0),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.dropEvent(event)

    assert event.isAccepted()
    assert "Unsupported source format" in window.status_bar.currentMessage()


def test_main_window_menu_add_queues_schema_work_once(tmp_path: Path, qtbot, monkeypatch) -> None:
    csv_file = tmp_path / "menu.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow(
        catalog_service=CatalogService(),
        file_dialog_service=FakeFileDialogService(paths=(csv_file,)),
    )
    qtbot.addWidget(window)
    monkeypatch.setattr(window._settings_service, "restore_profile_on_load", lambda: False)
    queued_schema_work: list[CatalogBinding] = []
    monkeypatch.setattr(window, "_queue_schema_work", queued_schema_work.append)

    window.desktop_actions.add_datasets.trigger()

    assert len(queued_schema_work) == 1


def test_main_window_reports_a_skipped_duplicate_dataset(tmp_path: Path, qtbot) -> None:
    csv_file = tmp_path / "already-loaded.csv"
    csv_file.write_text("id\n1\n")
    catalog_service = CatalogService()
    catalog_service.add_paths((csv_file,))
    window = MainWindow(catalog_service=catalog_service)
    qtbot.addWidget(window)

    window.catalog.add_paths((csv_file,))

    message = window.status_bar.currentMessage()
    assert "duplicate" in message.lower()
    assert "already-loaded.csv" in message


def test_main_window_reports_added_and_skipped_datasets_together(tmp_path: Path, qtbot) -> None:
    duplicate = tmp_path / "duplicate.csv"
    new_dataset = tmp_path / "new.csv"
    duplicate.write_text("id\n1\n")
    new_dataset.write_text("id\n2\n")
    catalog_service = CatalogService()
    catalog_service.add_paths((duplicate,))
    window = MainWindow(catalog_service=catalog_service)
    qtbot.addWidget(window)

    window.catalog.add_paths((duplicate, new_dataset))

    message = window.status_bar.currentMessage()
    assert "Added `new` to catalog." in message
    assert "duplicate" in message.lower()
    assert "duplicate.csv" in message


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


def test_main_window_copy_shortcut_uses_the_focused_translation_or_editor_widget(qtbot) -> None:
    """Ctrl+C must copy from the actual focused widget, not always the SQL editor."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(1)

    window.editor.setText("EDITOR SQL HERE")
    tabs = window.findChild(QTabWidget, "results_tabs")
    translation_edit = window.translation_panel.findChild(QPlainTextEdit)
    clipboard = QApplication.clipboard()

    assert tabs is not None
    assert translation_edit is not None
    assert clipboard is not None
    menu_copy_action = next(
        action for action in window.edit_menu.actions() if action.text() == "Copy"
    )
    assert menu_copy_action is not window.editor.edit_actions[3]

    tabs.setCurrentIndex(tabs.indexOf(window.translation_panel.parentWidget()))
    translation_edit.setPlainText("TRANSLATED SQL HERE")
    translation_edit.selectAll()
    translation_edit.setFocus(Qt.FocusReason.MouseFocusReason)
    assert QApplication.focusWidget() is translation_edit
    qtbot.keyClick(translation_edit, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert clipboard.text() == "TRANSLATED SQL HERE"
    assert clipboard.text() != "EDITOR SQL HERE"

    window.editor.selectAll()
    window.editor.setFocus(Qt.FocusReason.MouseFocusReason)
    assert QApplication.focusWidget() is window.editor
    qtbot.keyClick(window.editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert clipboard.text() == "EDITOR SQL HERE"


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
    window.preview_limit_selector.setText("250")
    window.preferences_action.trigger()
    window.preferences_dialog.editor_theme_selector.setCurrentText("Light")
    window.preferences_dialog.accept()
    window.editor.setText("SELECT 1")
    window.desktop_actions.run.setEnabled(True)  # isolated request-builder test without a catalog

    window.desktop_actions.run.trigger()

    assert submitted[0].preview_limit == 250
    assert settings.restore_preview_limit() == 250
    assert settings.restore_editor_theme() == "Light"


def test_main_window_preview_limit_text_box_validates_and_uses_last_valid_value(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    settings = _configure_qsettings_path(tmp_path / "preview-limit-validation")
    window = MainWindow(settings_service=settings)
    qtbot.addWidget(window)
    selector = window.preview_limit_selector

    assert isinstance(selector, QLineEdit)
    assert selector.text() == "1000"

    for valid_text in ("10", "500", "50000", "100000"):
        selector.setText(valid_text)
        assert settings.restore_preview_limit() == int(valid_text)
        assert selector.property("validationState") == "valid"

    selector.setText("50000")

    for invalid_text in ("5", "999999", "abc", ""):
        selector.setText(invalid_text)
        assert selector.property("validationState") == "invalid"
        assert "10" in selector.toolTip()
        assert "100000" in selector.toolTip()
        assert settings.restore_preview_limit() == 50000

    submitted: list[ExecutionRequest] = []
    monkeypatch.setattr(window.query_controller, "execute", submitted.append)
    window.editor.setText("SELECT 1")
    window.desktop_actions.run.setEnabled(True)
    window.desktop_actions.run.trigger()

    assert submitted[0].preview_limit == 50000

    restored = MainWindow(settings_service=settings)
    qtbot.addWidget(restored)
    assert restored.preview_limit_selector.text() == "50000"


def test_main_window_fills_starter_query_for_first_dataset_when_editor_is_empty(
    tmp_path: Path, qtbot
) -> None:
    csv_file = tmp_path / "select.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow(file_dialog_service=FakeFileDialogService(paths=(csv_file,)))
    qtbot.addWidget(window)

    window.desktop_actions.add_datasets.trigger()

    assert window.editor.text() == 'SELECT * FROM "select"'
    assert "LIMIT" not in window.editor.text().upper()


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

    window._settings_service.save_export_format(export_format.value)
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


def test_history_record_restore_replaces_editor_text_in_one_undo_action(
    tmp_path: Path, qtbot
) -> None:
    history = HistoryManager(storage_path=tmp_path / "history.json")
    history.add_entry("duckdb", "select * from history_record")
    window = MainWindow(history_manager=history)
    qtbot.addWidget(window)
    window.editor.setText("select * from original")

    window.history_dock.record_selected.emit(history.get_all()[0])

    assert window.editor.text() == "select * from history_record"
    assert window.editor.isUndoAvailable()

    window.editor.undo()

    assert window.editor.text() == "select * from original"


def test_main_window_saves_selected_history_records_as_sql(tmp_path: Path, qtbot) -> None:
    history = HistoryManager(storage_path=tmp_path / "history.json")
    history.add_entry("duckdb", "SELECT first")
    history.add_entry("duckdb", "SELECT second")
    records = history.get_all()
    destination = tmp_path / "selected-history"
    window = MainWindow(
        history_manager=history,
        file_dialog_service=FakeFileDialogService(paths=(), history_sql_path=destination),
    )
    qtbot.addWidget(window)

    for row in range(window.history_dock.history_table.topLevelItemCount()):
        item = window.history_dock.history_table.topLevelItem(row)
        assert item is not None
        item.setSelected(True)

    window.history_dock._save_as_sql_action.trigger()

    saved_file = destination.with_suffix(".sql")
    assert saved_file.read_text() == serialise_history_records_to_sql(records)


def test_main_window_cancelled_history_sql_save_creates_no_file(tmp_path: Path, qtbot) -> None:
    history = HistoryManager(storage_path=tmp_path / "history.json")
    history.add_entry("duckdb", "SELECT cancelled")
    destination = tmp_path / "cancelled-history.sql"
    window = MainWindow(
        history_manager=history,
        file_dialog_service=FakeFileDialogService(paths=()),
    )
    qtbot.addWidget(window)
    item = window.history_dock.history_table.topLevelItem(0)
    assert item is not None
    item.setSelected(True)

    window.history_dock._save_as_sql_action.trigger()

    assert not destination.exists()


def test_history_record_restore_leaves_existing_catalog_and_schema_work_untouched(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    initial = tmp_path / "already_loaded.csv"
    initial.write_text("id\n1\n")
    historical = tmp_path / "historical.csv"
    historical.write_text("id\n2\n")
    history = HistoryManager(storage_path=tmp_path / "history.json")
    history.add_entry(
        "duckdb",
        "SELECT restored_query",
        catalog={"historical": str(historical)},
    )
    catalog_service = CatalogService()
    catalog_service.add_paths((initial,))
    window = MainWindow(history_manager=history, catalog_service=catalog_service)
    qtbot.addWidget(window)
    entries_before = window._catalog_service.entries
    queued_schema_work: list[CatalogBinding] = []
    monkeypatch.setattr(window, "_queue_schema_work", queued_schema_work.append)

    window.history_dock.record_selected.emit(history.get_all()[0])

    assert window.editor.text() == "SELECT restored_query"
    assert window._catalog_service.entries == entries_before
    assert queued_schema_work == []


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
    service.save_window_layout_version(MainWindow.LAYOUT_SCHEMA_VERSION)
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


def test_main_window_elapsed_timer_reports_query_duration_and_stops_on_terminal_states(
    qtbot, monkeypatch
) -> None:
    current_time = [100.0]
    monkeypatch.setattr(main_window.time, "monotonic", lambda: current_time[0])
    window = MainWindow()
    qtbot.addWidget(window)

    assert not window._elapsed_timer.isActive()

    window._on_query_status_changed(ExecutionStatus.RUNNING)
    assert window._elapsed_timer.isActive()
    current_time[0] = 103.9
    window._update_elapsed_status()
    assert window.status_bar.currentMessage() == "Executing query... (3s)"

    for terminal_status in (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    ):
        window._on_query_status_changed(ExecutionStatus.RUNNING)
        assert window._elapsed_timer.isActive()
        window._on_query_status_changed(terminal_status)
        assert not window._elapsed_timer.isActive()


def test_main_window_elapsed_timer_preserves_cancellation_status(qtbot, monkeypatch) -> None:
    current_time = [100.0]
    monkeypatch.setattr(main_window.time, "monotonic", lambda: current_time[0])
    window = MainWindow()
    qtbot.addWidget(window)

    window._on_query_status_changed(ExecutionStatus.RUNNING)
    current_time[0] = 103.9
    window._on_query_status_changed(ExecutionStatus.CANCELLATION_REQUESTED)
    window._update_elapsed_status()

    assert "cancell" in window.status_bar.currentMessage().lower()
    assert "Executing query..." not in window.status_bar.currentMessage()


def test_main_window_close_stops_elapsed_timer(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._on_query_status_changed(ExecutionStatus.RUNNING)

    window.close()

    assert not window._elapsed_timer.isActive()


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


def test_main_window_close_bounds_worker_wait_and_saves_settings_on_timeout(
    qtbot, monkeypatch
) -> None:
    events: list[object] = []

    class NeverFinishesWorker(SchemaWorker):
        def __init__(self) -> None:
            QThread.__init__(self)

        def isRunning(self) -> bool:
            return True

        def quit(self) -> None:
            events.append("quit")

        def _fake_wait(self, *args: object) -> bool:
            events.append(("wait", args[0] if args else -1))
            return False

        def __getattribute__(self, name: str) -> object:
            if name == "wait":
                return object.__getattribute__(self, "_fake_wait")
            return super().__getattribute__(name)

    window = MainWindow()
    qtbot.addWidget(window)
    window._schema_workers = [NeverFinishesWorker()]
    monkeypatch.setattr(window.query_controller, "cancel", lambda: events.append("query_cancel"))
    monkeypatch.setattr(window.export_controller, "cancel", lambda: events.append("export_cancel"))
    monkeypatch.setattr(window.query_controller, "shutdown", lambda: True)
    monkeypatch.setattr(window.export_controller, "shutdown", lambda: True)
    saved_settings: list[str] = []
    for method_name in (
        "save_window_geometry",
        "save_window_state",
        "save_splitter_sizes",
        "save_editor_font_size",
    ):
        monkeypatch.setattr(
            window._settings_service,
            method_name,
            lambda *args, method_name=method_name: saved_settings.append(method_name),
        )

    window.close()

    assert events[:4] == ["query_cancel", "export_cancel", "quit", ("wait", 5000)]
    assert set(saved_settings) == {
        "save_window_geometry",
        "save_window_state",
        "save_splitter_sizes",
        "save_editor_font_size",
    }
    assert window.status_bar.currentMessage() == ""


def test_main_window_removes_completed_profile_workers(qtbot, tmp_path: Path) -> None:
    csv_file = tmp_path / "profile.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow()
    qtbot.addWidget(window)

    window._queue_profile_work(CatalogBinding(uuid4(), "profile", csv_file, SourceFormat.CSV))

    qtbot.waitUntil(lambda: not window._profile_workers, timeout=5000)
    assert window._profile_workers == []


def test_manual_profile_bypasses_over_limit_auto_profile_gate_and_updates_schema_panel(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    csv_file = tmp_path / "over-limit-profile.csv"
    profile_source_bytes = _write_large_profile_dataset(csv_file, row_count=250_000)
    assert profile_source_bytes > 5_000_000
    window = MainWindow()
    qtbot.addWidget(window)
    window._settings_service.save_profile_max_bytes(profile_source_bytes // 2)
    monkeypatch.setattr(window, "_queue_schema_work", lambda _binding: None)

    window.catalog.add_paths((csv_file,))

    entry = window._catalog_service.entries[0]
    assert entry.profile is None
    assert entry.profile_skipped_reason is not None
    assert "size limit" in entry.profile_skipped_reason
    assert window._profile_workers == []

    window._catalog_service.update_schema(
        SchemaResult(entry.id, (ColumnSchema("id", "BIGINT"), ColumnSchema("name", "VARCHAR")))
    )
    window.schema_panel.set_entries(window._catalog_service.entries, entry.alias)
    window.schema_panel.profile_button.click()
    assert len(window._profile_workers) == 1
    qtbot.waitUntil(lambda: not window._profile_workers, timeout=5000)
    assert "profiling skipped" not in window.schema_panel.warning_text().lower()

    profiled_entry = window._catalog_service.entries[0]
    assert profiled_entry.profile is not None
    assert window.schema_panel.cell_text(0, 5)
    assert window.schema_panel.cell_text(0, 4)
    assert window.schema_panel.cell_text(1, 6)
    assert window.schema_panel.cell_text(1, 5)


def test_main_window_profile_failure_keeps_skip_notice_until_success_clears(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    csv_file = tmp_path / "profile-failure-preserves-skip.csv"
    csv_file.write_text("id,name\n1,alpha\n2,beta\n")
    window = MainWindow()
    qtbot.addWidget(window)
    window._settings_service.save_profile_max_bytes(0)
    monkeypatch.setattr(window, "_queue_schema_work", lambda _binding: None)
    window.catalog.add_paths((csv_file,))
    entry = window._catalog_service.entries[0]

    window._catalog_service.update_schema(
        SchemaResult(
            entry.id,
            (
                ColumnSchema("id", "BIGINT"),
                ColumnSchema("name", "VARCHAR"),
            ),
        )
    )
    window.schema_panel.set_entries(window._catalog_service.entries, entry.alias)
    window._engine_registry = cast(
        Any,
        _ProfileRegistry(
            [
                ProfileResult(
                    entry.id,
                    profiles=None,
                    error_message="profiling exploded",
                ),
                ProfileResult(
                    entry.id,
                    profiles=(
                        ColumnProfile(
                            name="id",
                            data_type="BIGINT",
                            min="1",
                            max="2",
                            approx_unique=2,
                            avg="1.5",
                            std=None,
                            q25=None,
                            q50=None,
                            q75=None,
                            count=2,
                            null_percentage=0.0,
                        ),
                        ColumnProfile(
                            name="name",
                            data_type="VARCHAR",
                            min="alpha",
                            max="beta",
                            approx_unique=2,
                            avg=None,
                            std=None,
                            q25=None,
                            q50=None,
                            q75=None,
                            count=2,
                            null_percentage=0.0,
                        ),
                    ),
                ),
            ]
        ),
    )
    window.schema_panel.profile_button.click()

    qtbot.waitUntil(
        lambda: "Profiling failed: profiling exploded" in window.schema_panel.warning_text(),
        timeout=5000,
    )
    failed_entry = window._catalog_service.entries[0]
    assert "profiling skipped" in window.schema_panel.warning_text().lower()
    assert failed_entry.profile_skipped_reason is not None
    qtbot.waitUntil(lambda: window.schema_panel.profile_button.isEnabled(), timeout=5000)

    window.schema_panel.profile_button.click()
    qtbot.waitUntil(lambda: not window._profile_workers, timeout=5000)
    successful_entry = window._catalog_service.entries[0]
    assert successful_entry.profile_skipped_reason is None
    assert "profiling failed: profiling exploded" not in window.schema_panel.warning_text().lower()
    assert "profiling skipped" not in window.schema_panel.warning_text().lower()


def test_main_window_profile_failure_reaches_schema_panel_and_keeps_columns_visible(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    csv_file = tmp_path / "profile-failure.csv"
    csv_file.write_text("id,name\n1,alpha\n2,beta\n")
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr(window._settings_service, "restore_profile_on_load", lambda: False)
    monkeypatch.setattr(window, "_queue_schema_work", lambda _binding: None)
    window.catalog.add_paths((csv_file,))
    entry = window._catalog_service.entries[0]

    window._catalog_service.update_schema(
        SchemaResult(entry.id, (ColumnSchema("id", "BIGINT"), ColumnSchema("name", "VARCHAR")))
    )
    window.schema_panel.set_entries(window._catalog_service.entries, entry.alias)

    registry = _ProfileRegistry(
        [ProfileResult(entry.id, profiles=None, error_message="profiling exploded")],
    )
    window._engine_registry = cast(Any, registry)
    window.schema_panel.profile_button.click()

    qtbot.waitUntil(
        lambda: "Profiling failed: profiling exploded" in window.schema_panel.warning_text(),
        timeout=5000,
    )
    assert window.schema_panel._table_widget.isVisible()
    assert window.schema_panel.column_count_rows() == 2
    assert "profiling failed: profiling exploded" in window.schema_panel.warning_text().lower()
    qtbot.waitUntil(lambda: window.schema_panel.profile_button.isEnabled(), timeout=5000)
    assert "profiling..." not in window.schema_panel.warning_text().lower()


def test_main_window_profile_pending_state_is_visible_and_single_queued(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    csv_file = tmp_path / "profile-pending.csv"
    csv_file.write_text("id,name\n1,alpha\n2,beta\n")
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window._settings_service, "restore_profile_on_load", lambda: False)
    monkeypatch.setattr(window, "_queue_schema_work", lambda _binding: None)
    window.catalog.add_paths((csv_file,))
    entry = window._catalog_service.entries[0]

    window._catalog_service.update_schema(
        SchemaResult(
            entry.id,
            (
                ColumnSchema("id", "BIGINT"),
                ColumnSchema("name", "VARCHAR"),
            ),
        )
    )
    window.schema_panel.set_entries(window._catalog_service.entries, entry.alias)
    window._engine_registry = cast(
        Any,
        _ProfileRegistry(
            [
                ProfileResult(
                    entry.id,
                    profiles=(
                        ColumnProfile(
                            name="id",
                            data_type="BIGINT",
                            min="1",
                            max="2",
                            approx_unique=2,
                            avg="1.5",
                            std=None,
                            q25=None,
                            q50=None,
                            q75=None,
                            count=2,
                            null_percentage=0.0,
                        ),
                        ColumnProfile(
                            name="name",
                            data_type="VARCHAR",
                            min="alpha",
                            max="beta",
                            approx_unique=2,
                            avg=None,
                            std=None,
                            q25=None,
                            q50=None,
                            q75=None,
                            count=2,
                            null_percentage=0.0,
                        ),
                    ),
                    error_message=None,
                    error_type=None,
                )
            ],
            delay=0.25,
        ),
    )

    window.schema_panel.profile_button.click()
    qtbot.waitUntil(lambda: "profiling" in window.schema_panel.warning_text().lower(), timeout=5000)
    assert not window.schema_panel.profile_button.isEnabled()
    assert len(window._profile_workers) == 1

    window.schema_panel.profile_button.click()
    assert len(window._profile_workers) == 1

    qtbot.waitUntil(lambda: not window._profile_workers, timeout=5000)
    qtbot.waitUntil(lambda: window.schema_panel.profile_button.isEnabled(), timeout=5000)
    assert "profiling" not in window.schema_panel.warning_text().lower()
    assert window.schema_panel.cell_text(0, 4)
    assert window.schema_panel.column_count_rows() == 2


def test_main_window_profile_result_from_inactive_entry_does_not_replace_view(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("id\n1\n")
    second.write_text("id\n2\n")
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_queue_schema_work", lambda _binding: None)
    window.catalog.add_paths((first, second))
    first_entry = window._catalog_service.entries[0]
    second_entry = window._catalog_service.entries[1]

    window._catalog_service.update_schema(
        SchemaResult(first_entry.id, (ColumnSchema("id", "BIGINT"),))
    )
    window._catalog_service.update_schema(
        SchemaResult(second_entry.id, (ColumnSchema("id", "BIGINT"),)),
    )
    window.schema_panel.set_entries(window._catalog_service.entries, first_entry.alias)
    registry = _ProfileRegistry(
        [ProfileResult(second_entry.id, profiles=None, error_message="second dataset failed")]
    )
    window._engine_registry = cast(Any, registry)
    window._queue_profile_work(
        CatalogBinding(
            entry_id=second_entry.id,
            alias=second_entry.alias,
            path=second_entry.path,
            source_format=second_entry.source_format,
        )
    )
    qtbot.waitUntil(lambda: not window._profile_workers, timeout=5000)

    assert first_entry.alias in window.schema_panel.status_text()
    assert window.schema_panel.column_count_rows() == 1
    assert "second dataset failed" not in window.schema_panel.status_text().lower()


def test_main_window_close_waits_for_running_profile_workers(qtbot, tmp_path: Path) -> None:
    csv_file = tmp_path / "profile.csv"
    csv_file.write_text("id\n1\n")
    window = MainWindow()
    qtbot.addWidget(window)
    window._queue_profile_work(CatalogBinding(uuid4(), "profile", csv_file, SourceFormat.CSV))

    assert len(window._profile_workers) == 1
    window.close()
    assert window._profile_workers == []


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
    window.show()
    qtbot.wait(20)

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
    assert not window.empty_result_banner.isVisible()

    # 1b. A successful query with no rows has a distinct empty-result state.
    res_empty = QueryResult(
        request_id=req_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame(),
        execution_seconds=0.02,
        preview_row_count=0,
        total_row_count=0,
        truncated=False,
        completed_at=now,
    )
    window._on_query_result_ready(res_empty, request)
    assert window.empty_result_banner.isVisible()
    assert window.empty_result_banner.text() == "Query returned 0 rows."

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
    assert not window.empty_result_banner.isVisible()
    assert not window.result_error_message.isHidden()
    assert "near SELECT" in window.result_error_message.text()
    msg, severity = window.messages_panel.message_at(0)
    assert "Error (SyntaxError): near SELECT" in msg
    assert severity == "error"

    # A following success replaces the error in the results area.
    window._on_query_result_ready(res_success, request)
    assert not window.result_error_message.isVisible()
    assert window.result_error_message.text() == ""

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
    assert not window.empty_result_banner.isVisible()
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


def test_main_window_apply_order_to_query_replaces_editor_text_in_one_undo_action(
    qtbot, monkeypatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.editor.setText("SELECT * FROM users")
    window.result_table_view.set_frame(pl.DataFrame({"id": [1, 2]}))
    monkeypatch.setattr(window.query_controller, "execute", lambda _request: True)

    window._on_apply_query_order("id", "ASC")

    assert window.editor.text() == "SELECT * FROM users ORDER BY id ASC"
    assert window.editor.isUndoAvailable()

    window.editor.undo()

    assert window.editor.text() == "SELECT * FROM users"


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


def test_main_window_editor_shortcuts_survive_scintilla_key_bindings(qtbot) -> None:
    """Ctrl+T and Ctrl+/ must reach the desktop actions, not Scintilla's own commands."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    QTest.qWaitForWindowExposed(window)  # ty: ignore[no-matching-overload]  # QTest stubs model self.

    editor = window.current_editor
    assert editor is not None
    editor.setText("SELECT first\nSELECT second")
    editor.setCursorPosition(1, 0)
    editor.setFocus()
    assert QApplication.focusWidget() is editor

    QTest.keyClick(  # ty: ignore[no-matching-overload]  # QTest stubs model self.
        editor,
        Qt.Key.Key_T,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert window.editor_tabs.count() == 2
    assert editor.text() == "SELECT first\nSELECT second"

    second_editor = window.current_editor
    assert second_editor is not None
    second_editor.setText("SELECT second_tab")
    second_editor.setCursorPosition(0, 0)
    second_editor.setFocus()

    QTest.keyClick(  # ty: ignore[no-matching-overload]  # QTest stubs model self.
        second_editor,
        Qt.Key.Key_Slash,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert second_editor.text() == "-- SELECT second_tab"


def test_main_window_shows_and_clears_result_selection_statistics(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.result_table_view.set_frame(pl.DataFrame({"number": [1, 2]}))

    assert window.result_selection_stats_label.isHidden()
    selection_model = window.result_table_view.selectionModel()
    assert selection_model is not None
    selection_model.select(
        QItemSelection(
            window.result_table_view.proxy_model().index(0, 0),
            window.result_table_view.proxy_model().index(1, 0),
        ),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )

    assert not window.result_selection_stats_label.isHidden()
    assert window.result_selection_stats_label.text() == (
        "2 cells · 2 distinct · Sum: 3 · Mean: 1.5 · Min: 1 · Max: 2"
    )

    selection_model.clearSelection()

    assert window.result_selection_stats_label.isHidden()
