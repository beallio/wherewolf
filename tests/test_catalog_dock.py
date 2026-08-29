from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QItemSelectionModel, QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent, QFontMetrics
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QDockWidget, QHeaderView, QMenu, QTableView

import wherewolf.desktop.widgets.catalog_dock as catalog_dock_module
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


def _catalog_dock_with_datasets(
    qtbot, paths: tuple[Path, ...]
) -> tuple[CatalogDock, CatalogService]:
    service = CatalogService()
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("a\n1\n")
    dock.add_paths(paths)
    qtbot.waitUntil(lambda: dock.model.rowCount() == len(paths))
    dock.resize(900, 400)
    dock.show()
    QApplication.processEvents()
    return dock, service


def _select_catalog_cells(dock: CatalogDock, cells: tuple[tuple[int, int], ...]) -> None:
    selection_model = dock.view.selectionModel()
    assert selection_model is not None
    selection_model.clearSelection()
    for row, column in cells:
        selection_model.select(
            dock.model.index(row, column), QItemSelectionModel.SelectionFlag.Select
        )
    row, column = cells[-1]
    selection_model.setCurrentIndex(
        dock.model.index(row, column), QItemSelectionModel.SelectionFlag.NoUpdate
    )


def _open_catalog_context_menu(dock: CatalogDock, row: int, monkeypatch) -> None:
    monkeypatch.setattr(QMenu, "popup", lambda self, position: None)
    point = dock.view.visualRect(dock.model.index(row, 1)).center()
    dock._on_context_menu(point)


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


def test_catalog_all_columns_are_user_resizable(qtbot) -> None:
    dock = CatalogDock(CatalogService())
    qtbot.addWidget(dock)
    dock.show()

    view = dock.view
    header = view.horizontalHeader()
    assert header is not None

    for column in range(dock.model.columnCount()):
        assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
        before = header.sectionSize(column)
        header.resizeSection(column, before + 37)
        assert header.sectionSize(column) == before + 37

    assert isinstance(view.itemDelegateForColumn(2), FolderColumnDelegate)


def test_catalog_default_column_widths_are_applied(qtbot) -> None:
    dock = CatalogDock(CatalogService())
    qtbot.addWidget(dock)

    header = dock.view.horizontalHeader()
    assert header is not None
    assert (
        tuple(header.sectionSize(column) for column in range(dock.model.columnCount()))
        == CatalogDock.DEFAULT_COLUMN_WIDTHS
    )


def test_catalog_widening_the_dock_leaves_user_column_widths_alone(qtbot) -> None:
    dock = CatalogDock(CatalogService())
    qtbot.addWidget(dock)
    dock.resize(700, 200)
    dock.show()
    QApplication.processEvents()

    header = dock.view.horizontalHeader()
    assert header is not None
    before = tuple(header.sectionSize(column) for column in range(dock.model.columnCount()))
    dock.resize(1200, 200)
    QApplication.processEvents()

    assert tuple(header.sectionSize(column) for column in range(dock.model.columnCount())) == before


def test_catalog_right_click_targets_the_clicked_row_not_the_current_row(
    qtbot, monkeypatch
) -> None:
    service = CatalogService()
    service.add_paths(
        (
            Path("/datasets/alpha.csv"),
            Path("/datasets/bravo.csv"),
            Path("/datasets/charlie.csv"),
            Path("/datasets/delta.csv"),
        )
    )
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    dock.resize(900, 400)
    dock.show()
    QApplication.processEvents()
    monkeypatch.setattr(QMenu, "popup", lambda self, position: None)

    view = dock.view
    view.selectRow(0)
    point = view.visualRect(dock.model.index(3, 1)).center()
    dock._on_context_menu(point)

    selection = dock._selected_entry()
    assert selection is not None
    assert selection[0].alias == "delta"
    assert selection[1] == 3


def test_catalog_right_click_on_an_unselected_row_selects_only_that_row(qtbot, monkeypatch) -> None:
    service = CatalogService()
    service.add_paths(
        (
            Path("/datasets/alpha.csv"),
            Path("/datasets/bravo.csv"),
            Path("/datasets/charlie.csv"),
            Path("/datasets/delta.csv"),
        )
    )
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    dock.resize(900, 400)
    dock.show()
    QApplication.processEvents()
    monkeypatch.setattr(QMenu, "popup", lambda self, position: None)

    view = dock.view
    view.selectRow(0)
    point = view.visualRect(dock.model.index(2, 1)).center()
    dock._on_context_menu(point)

    selection_model = view.selectionModel()
    assert selection_model is not None
    assert all(index.row() == 2 for index in selection_model.selectedIndexes())


def test_catalog_right_click_inside_the_existing_selection_preserves_it(qtbot, monkeypatch) -> None:
    service = CatalogService()
    service.add_paths(
        (
            Path("/datasets/alpha.csv"),
            Path("/datasets/bravo.csv"),
            Path("/datasets/charlie.csv"),
            Path("/datasets/delta.csv"),
        )
    )
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    dock.resize(900, 400)
    dock.show()
    QApplication.processEvents()
    monkeypatch.setattr(QMenu, "popup", lambda self, position: None)

    view = dock.view
    selection_model = view.selectionModel()
    assert selection_model is not None
    selection_model.setCurrentIndex(
        dock.model.index(1, 2), QItemSelectionModel.SelectionFlag.ClearAndSelect
    )
    point = view.visualRect(dock.model.index(1, 0)).center()
    dock._on_context_menu(point)

    assert {(index.row(), index.column()) for index in selection_model.selectedIndexes()} == {
        (1, 2)
    }
    selection = dock._selected_entry()
    assert selection is not None
    assert selection[1] == 1


def test_catalog_right_click_on_blank_space_disables_every_context_action(
    qtbot, monkeypatch
) -> None:
    service = CatalogService()
    service.add_paths(
        (
            Path("/datasets/alpha.csv"),
            Path("/datasets/bravo.csv"),
            Path("/datasets/charlie.csv"),
            Path("/datasets/delta.csv"),
        )
    )
    dock = CatalogDock(service)
    qtbot.addWidget(dock)
    dock.resize(900, 400)
    dock.show()
    QApplication.processEvents()
    monkeypatch.setattr(QMenu, "popup", lambda self, position: None)

    view = dock.view
    view.selectRow(0)
    viewport = view.viewport()
    assert viewport is not None
    point = QPoint(50, viewport.height() - 5)
    assert not view.indexAt(point).isValid()
    dock._on_context_menu(point)

    assert all(
        not action.isEnabled()
        for action in (
            dock._rename_action,
            dock._remove_action,
            dock._refresh_action,
            dock._copy_alias_action,
            dock._copy_path_action,
            dock._reveal_action,
            dock._insert_alias_action,
        )
    )


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


def test_catalog_selected_rows_dedupes_cells_from_the_same_row(qtbot, tmp_path: Path) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    _select_catalog_cells(dock, ((1, 0), (1, 2), (1, 4), (3, 1)))

    rows = [row for _, row in dock._selected_entries()]

    assert rows == [1, 3]


def test_catalog_remove_deletes_every_selected_dataset(qtbot, tmp_path: Path) -> None:
    dock, service = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    aliases = tuple(entry.alias for entry in service.entries)
    _select_catalog_cells(dock, ((0, 0), (2, 0)))

    dock._remove_action.trigger()

    assert tuple(entry.alias for entry in service.entries) == (aliases[1], aliases[3])


def test_catalog_remove_persists_once_for_a_batch(qtbot, tmp_path: Path) -> None:
    dock, service = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    notifications: list[object] = []
    service.subscribe(lambda: notifications.append(None))
    _select_catalog_cells(dock, ((0, 0), (1, 0), (2, 0)))

    dock._remove_action.trigger()

    assert len(notifications) == 1


def test_catalog_copy_alias_joins_selected_aliases_with_newlines(qtbot, tmp_path: Path) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    aliases = tuple(dock.model.entry_at(row).alias for row in range(4))
    _select_catalog_cells(dock, ((0, 0), (2, 0)))
    clipboard = QApplication.clipboard()
    assert clipboard is not None

    dock._copy_alias_action.trigger()

    assert clipboard.text() == f"{aliases[0]}\n{aliases[2]}"


def test_catalog_copy_path_joins_selected_paths_with_newlines(qtbot, tmp_path: Path) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    paths = tuple(dock.model.entry_at(row).path for row in range(4))
    _select_catalog_cells(dock, ((0, 0), (2, 0)))
    clipboard = QApplication.clipboard()
    assert clipboard is not None

    dock._copy_path_action.trigger()

    assert clipboard.text() == f"{paths[0]}\n{paths[2]}"


def test_catalog_copy_uses_view_row_order_not_click_order(qtbot, tmp_path: Path) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    aliases = tuple(dock.model.entry_at(row).alias for row in range(4))
    _select_catalog_cells(dock, ((2, 0), (0, 0)))
    clipboard = QApplication.clipboard()
    assert clipboard is not None

    dock._copy_alias_action.trigger()

    assert clipboard.text() == f"{aliases[0]}\n{aliases[2]}"


def test_catalog_insert_alias_joins_selected_aliases_with_commas(qtbot, tmp_path: Path) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    aliases = tuple(dock.model.entry_at(row).alias for row in range(4))
    _select_catalog_cells(dock, ((0, 0), (2, 0)))
    spy = QSignalSpy(dock.insert_alias_requested)

    dock._insert_alias_action.trigger()

    assert len(spy) == 1
    assert spy[0][0] == f"{aliases[0]}, {aliases[2]}"


def test_catalog_refresh_schema_emits_one_binding_per_selected_dataset(
    qtbot, tmp_path: Path
) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    entries = tuple(dock.model.entry_at(row) for row in range(4))
    _select_catalog_cells(dock, ((0, 0), (1, 0), (2, 0)))
    spy = QSignalSpy(dock.refresh_schema_requested)

    dock._refresh_action.trigger()

    assert len(spy) == 3
    assert [spy[index][0].entry_id for index in range(len(spy))] == [
        entries[0].id,
        entries[1].id,
        entries[2].id,
    ]


def test_catalog_rename_is_disabled_for_a_multi_row_selection(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    _select_catalog_cells(dock, ((0, 0), (2, 0)))

    _open_catalog_context_menu(dock, 0, monkeypatch)

    assert dock._rename_action.isEnabled() is False
    assert all(
        action.isEnabled()
        for action in (
            dock._remove_action,
            dock._refresh_action,
            dock._copy_alias_action,
            dock._copy_path_action,
            dock._insert_alias_action,
        )
    )


def test_catalog_rename_stays_enabled_for_a_single_row(qtbot, tmp_path: Path, monkeypatch) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    _select_catalog_cells(dock, ((1, 0),))

    _open_catalog_context_menu(dock, 1, monkeypatch)

    assert dock._rename_action.isEnabled() is True


def test_catalog_reveal_is_enabled_for_several_files_in_one_folder(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    _select_catalog_cells(dock, ((0, 0), (2, 0)))

    _open_catalog_context_menu(dock, 0, monkeypatch)

    assert dock._reveal_action.isEnabled() is True


def test_catalog_reveal_is_disabled_when_the_selection_spans_folders(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    first_folder = tmp_path / "first"
    second_folder = tmp_path / "second"
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        (
            first_folder / "dataset_0.csv",
            first_folder / "dataset_1.csv",
            second_folder / "dataset_2.csv",
            second_folder / "dataset_3.csv",
        ),
    )
    _select_catalog_cells(dock, ((0, 0), (2, 0)))

    _open_catalog_context_menu(dock, 0, monkeypatch)

    assert dock._reveal_action.isEnabled() is False


def test_catalog_reveal_opens_one_target_for_several_files_in_one_folder(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    dock, _ = _catalog_dock_with_datasets(
        qtbot,
        tuple(tmp_path / f"dataset_{index}.csv" for index in range(4)),
    )
    _select_catalog_cells(dock, ((0, 0), (1, 0)))
    calls: list[list[str]] = []
    monkeypatch.setattr(catalog_dock_module.subprocess, "Popen", calls.append)

    dock._reveal_action.trigger()

    assert len(calls) == 1


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
