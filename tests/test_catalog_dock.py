from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent, QFontMetrics
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QDockWidget, QHeaderView, QTableView

from wherewolf.desktop.main_window import MainWindow
from wherewolf.desktop.models import CatalogModel
from wherewolf.desktop.widgets import CatalogDock, FolderColumnDelegate
from wherewolf.domain import ColumnSchema, SchemaResult
from wherewolf.services import CatalogService

_DROP_EVENT_MIME_DATA_CACHE: list[QMimeData] = []


@pytest.fixture(autouse=True)
def _drain_schema_workers(qtbot):
    yield
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            qtbot.waitUntil(
                lambda target=widget: not any(w.isRunning() for w in target._schema_workers),
                timeout=3000,
            )


def _drop_event(urls: list[Path]) -> QDropEvent:
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(url)) for url in urls])
    _DROP_EVENT_MIME_DATA_CACHE.append(mime_data)
    return QDropEvent(
        QPointF(1.0, 1.0),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_main_window_uses_catalog_dock_tableview(qtbot) -> None:
    window = MainWindow(catalog_service=CatalogService())
    qtbot.addWidget(window)

    assert isinstance(window.dataset_catalog_dock, QDockWidget)
    assert window.dataset_catalog_dock.objectName() == "dataset_catalog_dock"
    dock_widget = cast(CatalogDock, window.dataset_catalog_dock.widget())
    assert isinstance(dock_widget.view, QTableView)
    assert isinstance(dock_widget.model, CatalogModel)
    assert dock_widget.model.rowCount() == 0


def test_catalog_file_column_keeps_basenames_visible_in_the_middle(qtbot) -> None:
    first_path = Path("/very/long/shared/prefix/directory/segments/customers.parquet")
    second_path = Path("/very/long/shared/prefix/directory/segments/loans.parquet")
    service = CatalogService()
    service.add_paths((first_path, second_path))
    dock = CatalogDock(service)
    qtbot.addWidget(dock)

    view = dock.view
    header = view.horizontalHeader()
    assert header is not None
    header.resizeSection(1, 258)
    font_metrics = QFontMetrics(view.font())
    available_width = header.sectionSize(1) - 8
    first_displayed = dock.model.data(dock.model.index(0, 1), Qt.ItemDataRole.DisplayRole)
    second_displayed = dock.model.data(dock.model.index(1, 1), Qt.ItemDataRole.DisplayRole)
    assert isinstance(first_displayed, str)
    assert isinstance(second_displayed, str)
    first_middle = font_metrics.elidedText(first_displayed, view.textElideMode(), available_width)
    second_middle = font_metrics.elidedText(second_displayed, view.textElideMode(), available_width)

    assert first_middle != second_middle, (
        f"identical middle-elided strings: {first_middle!r}, {second_middle!r}"
    )
    assert first_path.name in first_middle
    assert second_path.name in second_middle
    assert view.textElideMode() == Qt.TextElideMode.ElideMiddle


def test_catalog_file_column_is_resizable_and_folder_column_stretches(qtbot) -> None:
    dock = CatalogDock(CatalogService())
    qtbot.addWidget(dock)
    dock.show()

    view = dock.view
    header = view.horizontalHeader()
    assert header is not None

    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.ResizeToContents
    assert header.sectionResizeMode(4) == QHeaderView.ResizeMode.ResizeToContents

    dock.resize(450, 200)
    QApplication.processEvents()
    narrow_folder_width = header.sectionSize(2)
    dock.resize(650, 200)
    QApplication.processEvents()
    assert header.sectionSize(2) > narrow_folder_width

    header.resizeSection(1, 400)
    assert header.sectionSize(1) == 400
    assert isinstance(view.itemDelegateForColumn(2), FolderColumnDelegate)


def test_catalog_file_column_shows_complete_basenames_at_user_dock_width(qtbot) -> None:
    first_path = Path(
        "C:/Users/dbeall/OneDrive - Contoso/Documents/Analytics/2026/customers.parquet"
    )
    second_path = Path(
        "C:/Users/dbeall/OneDrive - Contoso/Documents/Analytics/2026/transactions_2026_q1.parquet"
    )
    service = CatalogService()
    service.add_paths((first_path, second_path))
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    dock.resize(450, 200)
    dock.show()
    QApplication.processEvents()

    view = dock.view
    header = view.horizontalHeader()
    assert header is not None
    available_width = header.sectionSize(1) - 8
    font_metrics = QFontMetrics(view.font())
    first_displayed = dock.model.data(dock.model.index(0, 1), Qt.ItemDataRole.DisplayRole)
    second_displayed = dock.model.data(dock.model.index(1, 1), Qt.ItemDataRole.DisplayRole)
    assert isinstance(first_displayed, str)
    assert isinstance(second_displayed, str)
    first_shown = font_metrics.elidedText(first_displayed, view.textElideMode(), available_width)
    second_shown = font_metrics.elidedText(second_displayed, view.textElideMode(), available_width)

    assert first_path.name in first_shown
    assert second_path.name in second_shown


def test_catalog_dock_drag_and_drop_adds_supported_files(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    first = tmp_path / "alpha.csv"
    second = tmp_path / "beta.csv"
    first.write_text("a\n1")
    second.write_text("a\n1")

    event = _drop_event([first, second])
    window.catalog.dropEvent(event)

    assert len(service.snapshot()) == 2
    assert event.isAccepted()


def test_catalog_dock_drag_and_drop_rejects_directories(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    dir_path = tmp_path / "drop_dir"
    dir_path.mkdir()

    event = _drop_event([dir_path])
    window.catalog.dropEvent(event)

    assert service.snapshot() == ()
    assert not event.isAccepted()


def test_catalog_dock_add_warnings_are_not_emitted_because_main_window_owns_surface(
    qtbot,
    tmp_path: Path,
) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    unsupported = tmp_path / "unsupported.xls"
    supported = tmp_path / "supported.csv"
    unsupported.write_text("a\n1")
    supported.write_text("a\n1")

    warning_spy = QSignalSpy(window.catalog.error_reported)

    event = _drop_event([unsupported, supported])
    window.catalog.dropEvent(event)

    assert len(service.snapshot()) == 1
    assert len(warning_spy) == 0


def test_catalog_dock_drag_drop_ignores_no_local_files(qtbot) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    message_spy = QSignalSpy(window.catalog.error_reported)
    event = _drop_event([])
    window.catalog.dropEvent(event)

    assert service.snapshot() == ()
    assert not event.isAccepted()
    assert len(message_spy) == 0


def test_catalog_dock_and_dialog_share_add_paths_service_call(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    service = CatalogService()
    calls: list[tuple[tuple[Path, ...]]] = []
    original = service.add_paths

    def spy(paths: tuple[Path, ...]):
        calls.append((paths,))
        return original(paths)

    monkeypatch.setattr(service, "add_paths", spy)

    first = tmp_path / "a.csv"
    first.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    window.catalog.dropEvent(_drop_event([first]))
    assert len(calls) == 1
    assert calls[0][0] == (first,)
    window.catalog.add_paths((first,))
    assert len(calls) == 2


def test_catalog_dock_drag_and_drop_deduplicates_resolved_paths(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    source = tmp_path / "data.csv"
    source.write_text("a\n1")
    duplicate = tmp_path / "alias.csv"
    duplicate.symlink_to(source)

    window.catalog.dropEvent(_drop_event([source, duplicate]))

    assert len(service.snapshot()) == 1


def test_main_window_drag_and_drop_is_forwarded_to_catalog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    service = CatalogService()
    calls: list[QDropEvent] = []

    def spy(event: QDropEvent) -> None:
        calls.append(event)

    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)
    monkeypatch.setattr(window.catalog, "dropEvent", spy)

    path = tmp_path / "a.csv"
    path.write_text("a\n1")
    event = _drop_event([path])
    window.dropEvent(event)

    assert calls
    assert calls[0] is event


def test_catalog_context_menu_copy_and_remove_actions(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    file_path = tmp_path / "a.csv"
    file_path.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)
    window.catalog.add_paths((file_path,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)

    window.catalog.view.selectRow(0)
    dock = window.catalog
    clipboard = QApplication.clipboard()
    assert clipboard is not None

    window.catalog._copy_alias_action.trigger()
    assert clipboard.text() == dock.model.entry_at(0).alias

    window.catalog._copy_path_action.trigger()
    assert clipboard.text() == str(dock.model.entry_at(0).path)

    dock._remove_action.trigger()
    assert len(service.snapshot()) == 0


def test_catalog_cell_selection_keeps_context_actions_on_the_clicked_entry(
    qtbot, tmp_path: Path
) -> None:
    service = CatalogService()
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first.write_text("a\n1")
    second.write_text("a\n1")
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    dock.add_paths((first, second))
    qtbot.waitUntil(lambda: dock.model.rowCount() == 2)
    dock.resize(700, 300)
    dock.show()

    first_alias = dock.model.entry_at(0).alias
    second_alias = dock.model.entry_at(1).alias
    clicked_index = dock.model.index(1, 1)
    qtbot.mouseClick(
        dock.view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        dock.view.visualRect(clicked_index).center(),
    )

    selection_model = dock.view.selectionModel()
    assert selection_model is not None
    selected_indexes = selection_model.selectedIndexes()
    assert len(selected_indexes) == 1
    assert selected_indexes[0] == clicked_index

    clipboard = QApplication.clipboard()
    assert clipboard is not None
    dock._copy_alias_action.trigger()
    assert clipboard.text() == second_alias

    dock._remove_action.trigger()
    assert tuple(entry.alias for entry in service.entries) == (first_alias,)


def test_catalog_vertical_header_click_selects_the_whole_row(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first.write_text("a\n1")
    second.write_text("a\n1")
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    dock.add_paths((first, second))
    qtbot.waitUntil(lambda: dock.model.rowCount() == 2)
    dock.resize(700, 300)
    dock.show()

    header = dock.view.verticalHeader()
    assert header is not None
    viewport = header.viewport()
    assert viewport is not None
    position = QPoint(
        viewport.width() // 2,
        header.sectionPosition(1) + header.sectionSize(1) // 2,
    )
    QTest.mouseClick(  # ty: ignore[no-matching-overload]  # QTest stubs model self.
        viewport,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        position,
    )

    selection_model = dock.view.selectionModel()
    assert selection_model is not None
    assert {(index.row(), index.column()) for index in selection_model.selectedIndexes()} == {
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    }


def test_catalog_context_menu_rename_error_message(qtbot, tmp_path: Path, monkeypatch) -> None:
    service = CatalogService()
    path = tmp_path / "a.csv"
    path.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    window.catalog.add_paths((path,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)
    window.catalog.view.selectRow(0)

    monkeypatch.setattr(
        "wherewolf.desktop.widgets.catalog_dock.QInputDialog.getText",
        lambda *_args, **_kwargs: ("123bad", True),
    )

    messages: list[str] = []
    monkeypatch.setattr(
        "wherewolf.desktop.widgets.catalog_dock.QMessageBox.warning",
        lambda *_args, **_kwargs: None,
    )
    window.catalog.error_reported.connect(messages.append)
    window.catalog._rename_action.trigger()

    assert messages
    assert "must be a SQL identifier" in messages[0]


def test_catalog_context_menu_rename_updates_alias_and_rejects_casefold_duplicate(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    service = CatalogService()
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first.write_text("a\n1")
    second.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)
    window.catalog.add_paths((first, second))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 2)
    window.catalog.view.selectRow(0)

    monkeypatch.setattr(
        "wherewolf.desktop.widgets.catalog_dock.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Renamed", True),
    )
    window.catalog._rename_action.trigger()
    assert service.entries[0].alias == "Renamed"

    with pytest.raises(ValueError, match="already exists"):
        service.rename(service.entries[1].id, "renamed")


def test_catalog_context_menu_refresh_schema_emits_binding(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    service.update_schema = Mock(wraps=service.update_schema)
    path = tmp_path / "a.csv"
    path.write_text("a\n1")

    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)
    window.catalog.add_paths((path,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)
    window.catalog.view.selectRow(0)

    spy = []
    window.catalog.refresh_schema_requested.connect(lambda binding: spy.append(binding))
    window.catalog._refresh_action.trigger()

    assert len(spy) == 1
    assert spy[0].alias == "a"


def test_catalog_dock_refresh_schema_updates_service_path(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    file_path = tmp_path / "a.csv"
    file_path.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    window.catalog.add_paths((file_path,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)

    service.update_schema(
        SchemaResult(
            entry_id=window.catalog.model.entry_at(0).id,
            columns=(ColumnSchema("a", "BIGINT"),),
        )
    )
    assert window.catalog.model.data(window.catalog.model.index(0, 4)) == "Ready"
