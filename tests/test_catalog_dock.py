from pathlib import Path

from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtWidgets import QDockWidget, QTableView

from wherewolf.desktop.main_window import MainWindow
from wherewolf.desktop.models import CatalogModel
from wherewolf.services import CatalogService


class _TestDropEvent:
    """Drop-event substitute used to avoid constructing native QDropEvent in tests."""

    def __init__(self, urls: list[Path]) -> None:
        self._accepted = False
        self._mime_data = QMimeData()
        self._mime_data.setUrls([QUrl.fromLocalFile(str(url)) for url in urls])

    def mimeData(self) -> QMimeData:
        return self._mime_data

    def acceptProposedAction(self) -> None:
        self._accepted = True

    def ignore(self) -> None:
        self._accepted = False

    def isAccepted(self) -> bool:
        return self._accepted


def _drop_urls(urls: list[Path]) -> _TestDropEvent:
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(url)) for url in urls])
    event = _TestDropEvent([])
    event._mime_data = mime_data
    return event


def test_main_window_uses_catalog_dock_tableview(qtbot) -> None:
    window = MainWindow(catalog_service=CatalogService())
    qtbot.addWidget(window)

    assert isinstance(window.dataset_catalog_dock, QDockWidget)
    assert window.dataset_catalog_dock.objectName() == "dataset_catalog_dock"
    dock_widget = window.dataset_catalog_dock.widget()
    assert dock_widget is not None
    assert hasattr(dock_widget, "view")
    assert isinstance(dock_widget.view, QTableView)
    assert isinstance(dock_widget.model, CatalogModel)
    assert dock_widget.model.rowCount() == 0


def test_catalog_dock_drag_and_drop_adds_supported_files(qtbot) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    first = Path("/tmp/alpha.csv")
    second = Path("/tmp/beta.csv")
    first.write_text("a\n1")
    second.write_text("a\n1")

    window.dropEvent(_drop_urls([first, second]))

    assert len(service.snapshot()) == 2


def test_catalog_dock_drag_and_drop_rejects_directories(qtbot) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    dir_path = Path("/tmp/drop_dir")
    dir_path.mkdir(exist_ok=True)
    event = _drop_urls([dir_path])

    window.dropEvent(event)
    assert service.snapshot() == ()
    assert not event.isAccepted()


def test_catalog_dock_drag_drop_unsupported_files_are_single_warning_and_still_add_supported(
    qtbot,
) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    unsupported = Path("/tmp/unsupported.xls")
    supported = Path("/tmp/supported.csv")
    unsupported.write_text("a\n1")
    supported.write_text("a\n1")

    messages: list[str] = []
    window.catalog_dock.error_reported.connect(messages.append)

    window.dropEvent(_drop_urls([unsupported, supported]))

    assert len(service.snapshot()) == 1
    assert len(messages) == 1
    assert "Unsupported source format" in messages[0]


def test_catalog_dock_drag_drop_ignores_no_local_files(qtbot) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    event = _drop_urls([])
    window.dropEvent(event)

    assert service.snapshot() == ()


def test_catalog_dock_and_dialog_share_add_paths_service_call(tmp_path, qtbot) -> None:
    service = CatalogService()
    calls: list[tuple[tuple[Path, ...]]] = []
    original = service.add_paths

    def spy(paths: tuple[Path, ...]):
        calls.append((paths,))
        return original(paths)

    service.add_paths = spy

    first = tmp_path / "a.csv"
    first.write_text("a\n1")
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    window.dropEvent(_drop_urls([first]))
    assert len(calls) == 1
    assert calls[0][0] == (first,)
    window.catalog_dock.add_paths((first,))
    assert len(calls) == 2


def test_catalog_dock_drag_and_drop_deduplicates_resolved_paths(tmp_path, qtbot) -> None:
    service = CatalogService()
    window = MainWindow(catalog_service=service)
    qtbot.addWidget(window)

    source = tmp_path / "data.csv"
    source.write_text("a\n1")
    duplicate = tmp_path / "alias.csv"
    duplicate.symlink_to(source)

    window.dropEvent(_drop_urls([source, duplicate]))

    assert len(service.snapshot()) == 1
