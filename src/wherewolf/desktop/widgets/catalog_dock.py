"""Dataset catalog panel with table view and actions."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from wherewolf.desktop.models import CatalogModel
from wherewolf.domain import CatalogEntry
from wherewolf.domain.models import CatalogBinding
from wherewolf.services import CatalogService


class CatalogDock(QWidget):
    """Single dockable catalog for browsing, filtering and mutating datasets."""

    insert_alias_requested = pyqtSignal(str)
    refresh_schema_requested = pyqtSignal(CatalogBinding)
    error_reported = pyqtSignal(str)

    def __init__(
        self,
        catalog_service: CatalogService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._catalog_service = catalog_service
        self._model = CatalogModel(catalog_service, self)
        self._model.rename_failed.connect(self.error_reported.emit)

        self._view = QTableView(self)
        self._view.setObjectName("catalog_view")
        self._view.setModel(self._model)
        self._view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        catalog_viewport = self._view.viewport()
        assert catalog_viewport is not None
        catalog_viewport.setAcceptDrops(True)
        catalog_viewport.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._rename_action = QAction("Rename Alias", self)
        self._remove_action = QAction("Remove", self)
        self._refresh_action = QAction("Refresh Schema", self)
        self._copy_alias_action = QAction("Copy Alias", self)
        self._copy_path_action = QAction("Copy File Path", self)
        self._insert_alias_action = QAction("Insert Alias at Editor Cursor", self)

        self._rename_action.triggered.connect(self._rename_selected_alias)
        self._remove_action.triggered.connect(self._remove_selected)
        self._refresh_action.triggered.connect(self._refresh_schema)
        self._copy_alias_action.triggered.connect(self._copy_alias)
        self._copy_path_action.triggered.connect(self._copy_path)
        self._insert_alias_action.triggered.connect(self._insert_alias)

        self.setAcceptDrops(True)

    @property
    def view(self) -> QTableView:
        return self._view

    @property
    def model(self) -> CatalogModel:
        return self._model

    def add_paths(self, paths: tuple[Path, ...]) -> None:
        report = self._catalog_service.add_paths(paths)
        if report.warnings:
            self.error_reported.emit("\n".join(sorted(set(report.warnings))))

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0 is None:
            return
        mime_data = a0.mimeData()
        if mime_data is None:
            return
        if self._can_accept_drop(mime_data):
            a0.acceptProposedAction()
        else:
            a0.ignore()

    def dropEvent(self, a0: QDropEvent | None) -> None:
        if a0 is None:
            return
        mime_data = a0.mimeData()
        if mime_data is None:
            return
        paths = self._extract_local_paths(mime_data)
        if not paths:
            a0.ignore()
            return
        self.add_paths(paths)
        a0.acceptProposedAction()

    def _can_accept_drop(self, mime_data: QMimeData) -> bool:
        paths = self._extract_local_paths(mime_data)
        return bool(paths)

    def _extract_local_paths(self, mime_data: QMimeData) -> tuple[Path, ...]:
        paths = []
        for url in mime_data.urls():
            if url.scheme() != "file":
                continue
            path = Path(url.toLocalFile())
            if not path.exists():
                continue
            if path.is_dir():
                return ()
            paths.append(path)
        return tuple(paths)

    def _selected_entry(self) -> tuple[CatalogEntry, int] | None:
        selection_model = self._view.selectionModel()
        if selection_model is None:
            return None
        indexes = selection_model.selectedRows()
        if not indexes:
            return None
        row = indexes[0].row()
        if row < 0 or row >= self._model.rowCount():
            return None
        return self._model.entry_at(row), row

    def _on_context_menu(self, position: QPoint) -> None:
        selection = self._selected_entry()
        menu = QMenu(self)
        menu.addAction(self._rename_action)
        menu.addAction(self._remove_action)
        menu.addAction(self._refresh_action)
        menu.addSeparator()
        menu.addAction(self._copy_alias_action)
        menu.addAction(self._copy_path_action)
        menu.addSeparator()
        menu.addAction(self._insert_alias_action)

        if selection is None:
            self._rename_action.setEnabled(False)
            self._remove_action.setEnabled(False)
            self._refresh_action.setEnabled(False)
            self._copy_alias_action.setEnabled(False)
            self._copy_path_action.setEnabled(False)
            self._insert_alias_action.setEnabled(False)
        else:
            self._rename_action.setEnabled(True)
            self._remove_action.setEnabled(True)
            self._refresh_action.setEnabled(True)
            self._copy_alias_action.setEnabled(True)
            self._copy_path_action.setEnabled(True)
            self._insert_alias_action.setEnabled(True)
        catalog_viewport = self._view.viewport()
        assert catalog_viewport is not None
        menu.popup(catalog_viewport.mapToGlobal(position))

    def _rename_selected_alias(self) -> None:
        selection = self._selected_entry()
        if selection is None:
            return
        entry, _ = selection

        alias, ok = QInputDialog.getText(
            self,
            "Rename alias",
            "Alias",
            text=entry.alias,
        )
        if not ok:
            return
        try:
            self._catalog_service.rename(entry.id, alias)
        except ValueError as err:
            self.error_reported.emit(str(err))
            QMessageBox.warning(self, "Rename Alias", str(err))

    def _remove_selected(self) -> None:
        selection = self._selected_entry()
        if selection is None:
            return
        entry, _ = selection
        self._catalog_service.remove(entry.id)

    def _refresh_schema(self) -> None:
        selection = self._selected_entry()
        if selection is None:
            return
        entry, _ = selection
        self.refresh_schema_requested.emit(
            CatalogBinding(
                entry_id=entry.id,
                alias=entry.alias,
                path=entry.path,
                source_format=entry.source_format,
            )
        )

    def _copy_alias(self) -> None:
        selection = self._selected_entry()
        if selection is None:
            return
        entry, _ = selection
        clipboard = QApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(entry.alias)

    def _copy_path(self) -> None:
        selection = self._selected_entry()
        if selection is None:
            return
        entry, _ = selection
        clipboard = QApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(str(entry.path))

    def _insert_alias(self) -> None:
        selection = self._selected_entry()
        if selection is None:
            return
        entry, _ = selection
        self.insert_alias_requested.emit(entry.alias)
