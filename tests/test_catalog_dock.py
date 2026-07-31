from pathlib import Path

from PyQt6.QtWidgets import QDockWidget, QTableView

from wherewolf.desktop.main_window import MainWindow
from wherewolf.services import CatalogService


def test_main_window_uses_catalog_dock_tableview(qtbot) -> None:
    window = MainWindow(catalog_service=CatalogService())
    qtbot.addWidget(window)

    assert isinstance(window.dataset_catalog_dock, QDockWidget)
    assert window.dataset_catalog_dock.objectName() == "dataset_catalog_dock"
    dock_widget = window.dataset_catalog_dock.widget()
    assert dock_widget is not None
    assert hasattr(dock_widget, "view")
    assert isinstance(dock_widget.view, QTableView)
    assert dock_widget.model.rowCount() == 0


def test_catalog_dock_add_paths_warnings_are_consolidated(qtbot) -> None:
    window = MainWindow(catalog_service=CatalogService())
    qtbot.addWidget(window)

    dock_widget = window.catalog_dock
    message = []
    dock_widget.error_reported.connect(message.append)

    supported = Path("/tmp/a.csv")
    unsupported = Path("/tmp/b.txt")

    dock_widget.add_paths((supported, unsupported))
    assert dock_widget.model.rowCount() == 1
    assert message
    assert "Unsupported source format" in message[0]
