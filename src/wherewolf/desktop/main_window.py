"""Main PyQt6 window for the desktop foundation shell."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMenu,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
)

from wherewolf.desktop.actions import DesktopActions, build_actions
from wherewolf.desktop.dialogs import FileDialogService, QtFileDialogService, FakeFileDialogService
from wherewolf.desktop.widgets import CatalogDock
from wherewolf.desktop.widgets.catalog_dock import CatalogDock as CatalogDockWidget
from wherewolf.services import CatalogService, SettingsService


class MainWindow(QMainWindow):
    """A stable, testable application shell for desktop migration phase 3."""

    def __init__(
        self,
        *,
        settings_service: SettingsService | None = None,
        actions: DesktopActions | None = None,
        catalog_service: CatalogService | None = None,
        file_dialog_service: FileDialogService | None = None,
    ) -> None:
        super().__init__()
        self._settings_service = settings_service or SettingsService()
        self._catalog_service = catalog_service or CatalogService()
        self._file_dialog_service = file_dialog_service or QtFileDialogService()
        self.desktop_actions = actions or build_actions(self)

        self.main_toolbar = self._build_toolbar()
        self._catalog_dock_widget = self._build_catalog_dock()
        self.dataset_catalog_dock = self._catalog_dock_widget
        self._central_splitter = self._build_central_area()
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.setCentralWidget(self._central_splitter)
        self._build_menus()
        self._restore_state()

    @property
    def catalog_dock(self) -> CatalogDock:
        widget = self._catalog_dock_widget.widget()
        assert isinstance(widget, CatalogDock)
        return widget

    @property
    def catalog_view(self) -> QTextEdit:
        return cast(QTextEdit, self._central_splitter.widget(0))

    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Primary", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.addAction(self.desktop_actions.run)
        toolbar.addAction(self.desktop_actions.cancel)
        toolbar.addAction(self.desktop_actions.format_sql)
        toolbar.addAction(self.desktop_actions.add_datasets)
        self.addToolBar(toolbar)
        return toolbar

    def _build_catalog_dock(self) -> QDockWidget:
        catalog = CatalogDock(self._catalog_service, self)
        dock = QDockWidget("Dataset Catalog", self)
        dock.setObjectName("dataset_catalog_dock")
        dock.setWidget(catalog)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        return dock

    def _build_central_area(self) -> QSplitter:
        editor = QTextEdit(self)
        editor.setObjectName("query_editor")
        editor.setPlaceholderText("Enter SQL query")

        results = QTabWidget(self)
        results.setObjectName("results_tabs")
        results.addTab(QTextEdit("Results pending"), "Results")

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setObjectName("central_splitter")
        splitter.addWidget(editor)
        splitter.addWidget(results)
        return splitter

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        assert menu_bar is not None
        file_menu = cast(QMenu, menu_bar.addMenu("File"))
        file_menu.setObjectName("file_menu")

        edit_menu = cast(QMenu, menu_bar.addMenu("Edit"))
        edit_menu.setObjectName("edit_menu")

        query_menu = cast(QMenu, menu_bar.addMenu("Query"))
        query_menu.setObjectName("query_menu")
        query_menu.addAction(self.desktop_actions.run)
        query_menu.addAction(self.desktop_actions.cancel)
        query_menu.addAction(self.desktop_actions.format_sql)

        view_menu = cast(QMenu, menu_bar.addMenu("View"))
        view_menu.setObjectName("view_menu")

        help_menu = cast(QMenu, menu_bar.addMenu("Help"))
        help_menu.setObjectName("help_menu")

        self.file_menu = file_menu
        self.edit_menu = edit_menu
        self.query_menu = query_menu
        self.view_menu = view_menu
        self.help_menu = help_menu

    def _restore_state(self) -> None:
        geometry = self._settings_service.restore_window_geometry()
        if geometry:
            self.restoreGeometry(QByteArray(geometry))

        state = self._settings_service.restore_window_state()
        if state:
            self.restoreState(QByteArray(state))

        sizes = self._settings_service.restore_splitter_sizes()
        if sizes:
            self._central_splitter.setSizes(list(sizes))

        font_size = self._settings_service.restore_editor_font_size()
        editor = self._central_splitter.widget(0)
        if editor is None:
            return

        font = editor.font()
        if not isinstance(font, QFont):
            return
        font.setPointSize(font_size)
        editor.setFont(font)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self._settings_service.save_window_geometry(self.saveGeometry().data())
        self._settings_service.save_window_state(self.saveState().data())
        self._settings_service.save_splitter_sizes(self._central_splitter.sizes())
        super().closeEvent(a0)
