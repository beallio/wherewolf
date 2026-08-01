from pathlib import Path
from typing import cast
from unittest.mock import Mock

from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication, QDockWidget, QTableView

from wherewolf.desktop.main_window import MainWindow
from wherewolf.desktop.models import CatalogModel
from wherewolf.desktop.widgets import CatalogDock
from wherewolf.domain import ColumnSchema, SchemaResult
from wherewolf.services import CatalogService

_DROP_EVENT_MIME_DATA_CACHE: list[QMimeData] = []


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
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))


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


def test_catalog_dock_drag_drop_unsupported_files_are_single_warning_and_still_add_supported(
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

    messages: list[str] = []
    window.catalog.error_reported.connect(messages.append)

    event = _drop_event([unsupported, supported])
    window.catalog.dropEvent(event)

    assert len(service.snapshot()) == 1
    assert len(messages) == 1
    assert "Unsupported source format" in messages[0]
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))


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
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))


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
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))


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
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))

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
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))


def test_catalog_context_menu_rename_error_message(qtbot, tmp_path: Path, monkeypatch) -> None:
    service = CatalogService()
    path = tmp_path / "a.csv"
    path.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    window.catalog.add_paths((path,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))
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
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))


def test_catalog_context_menu_refresh_schema_emits_binding(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    service.update_schema = Mock(wraps=service.update_schema)
    path = tmp_path / "a.csv"
    path.write_text("a\n1")

    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)
    window.catalog.add_paths((path,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))
    window.catalog.view.selectRow(0)

    spy = []
    window.catalog.refresh_schema_requested.connect(lambda binding: spy.append(binding))
    window.catalog._refresh_action.trigger()

    assert len(spy) == 1
    assert spy[0].alias == "a"
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))


def test_catalog_dock_refresh_schema_updates_service_path(qtbot, tmp_path: Path) -> None:
    service = CatalogService()
    file_path = tmp_path / "a.csv"
    file_path.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    window.catalog.add_paths((file_path,))
    qtbot.waitUntil(lambda: window.catalog.model.rowCount() == 1)
    qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))

    service.update_schema(
        SchemaResult(
            entry_id=window.catalog.model.entry_at(0).id,
            columns=(ColumnSchema("a", "BIGINT"),),
        )
    )
    assert window.catalog.model.data(window.catalog.model.index(0, 3)) == "Ready"
