from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QSettings
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
    assert isinstance(window.findChild(QSplitter), QSplitter)
    assert isinstance(window.findChild(QTabWidget), QTabWidget)
    assert isinstance(window.status_bar, QStatusBar)

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
    assert not format_action.isEnabled()

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

    assert run_action.shortcut().toString() == "Ctrl+Return"
    assert cancel_action.shortcut().toString() == "Ctrl+."


def test_main_window_recoverable_from_corrupt_settings(qtbot, tmp_path: Path) -> None:
    service = _configure_qsettings_path(tmp_path / "corrupt")
    service.save_window_state(b"state-value")
    service._settings.setValue(service.window_geometry_key, "garbage")

    window = MainWindow(settings_service=service)
    qtbot.addWidget(window)
    assert isinstance(window, QMainWindow)


def test_main_window_close_cleans_top_level_widgets() -> None:
    window = MainWindow()
    window.show()

    window.close()
    app = QCoreApplication.instance()
    assert app is not None
    app.processEvents()
    assert isinstance(app, QApplication)
    top_levels = [w for w in app.topLevelWidgets() if isinstance(w, QMainWindow)]
    assert not any(widget is window for widget in top_levels)
