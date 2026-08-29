"""Dataset catalog panel with table view and actions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from PyQt6.QtCore import QItemSelectionModel, QMimeData, QPoint, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from wherewolf.desktop.models import CatalogModel
from wherewolf.desktop.widgets.folder_column_delegate import FolderColumnDelegate
from wherewolf.domain import CatalogEntry
from wherewolf.domain.models import CatalogBinding
from wherewolf.services import CatalogService


class CatalogDock(QWidget):
    """Single dockable catalog for browsing, filtering and mutating datasets."""

    #: Default width per logical column; all columns are user-resizable from here.
    DEFAULT_COLUMN_WIDTHS: ClassVar[tuple[int, ...]] = (120, 220, 300, 90, 180)

    insert_alias_requested = pyqtSignal(str)
    refresh_schema_requested = pyqtSignal(CatalogBinding)
    datasets_added = pyqtSignal(object)
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
        assert len(self.DEFAULT_COLUMN_WIDTHS) == self._model.columnCount(), (
            "CatalogDock default widths must match CatalogModel columns"
        )

        self._view = QTableView(self)
        self._view.setObjectName("catalog_view")
        self._view.setModel(self._model)
        self._view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        header = self._view.horizontalHeader()
        if header is not None:
            header.setSectionsMovable(True)
            for column, width in enumerate(self.DEFAULT_COLUMN_WIDTHS):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
                header.resizeSection(column, width)
        self._folder_delegate = FolderColumnDelegate(self)
        self._view.setItemDelegateForColumn(2, self._folder_delegate)
        self._view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._view.setAlternatingRowColors(True)
        self._view.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._rename_action = QAction("Rename Alias", self)
        self._remove_action = QAction("Remove", self)
        self._refresh_action = QAction("Refresh Schema", self)
        self._copy_alias_action = QAction("Copy Alias", self)
        self._copy_path_action = QAction("Copy File Path", self)
        self._insert_alias_action = QAction("Insert Alias at Editor Cursor", self)
        self._reveal_action = QAction("Reveal in File Manager", self)

        self._rename_action.triggered.connect(self._rename_selected_alias)
        self._remove_action.triggered.connect(self._remove_selected)
        self._refresh_action.triggered.connect(self._refresh_schema)
        self._copy_alias_action.triggered.connect(self._copy_alias)
        self._copy_path_action.triggered.connect(self._copy_path)
        self._insert_alias_action.triggered.connect(self._insert_alias)
        self._reveal_action.triggered.connect(self._reveal_selected)

        self.setAcceptDrops(True)

    @property
    def view(self) -> QTableView:
        return self._view

    @property
    def model(self) -> CatalogModel:
        return self._model

    def add_paths(self, paths: tuple[Path, ...]) -> None:
        report = self._catalog_service.add_paths(paths)
        self.datasets_added.emit(report)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0 is None:
            return

        mime_data = a0.mimeData()
        if mime_data is None or not self._has_local_urls(mime_data):
            a0.ignore()
            return

        a0.acceptProposedAction()

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

    def _has_local_urls(self, mime_data: QMimeData) -> bool:
        for _ in self._extract_local_urls(mime_data):
            return True
        return False

    def _extract_local_paths(self, mime_data: QMimeData) -> tuple[Path, ...]:
        paths: list[Path] = []
        for url in self._extract_local_urls(mime_data):
            path = Path(url.toLocalFile())
            if path.is_dir() or not path.exists():
                continue
            paths.append(path)

        return tuple(paths)

    @staticmethod
    def _extract_local_urls(mime_data: QMimeData) -> tuple[QUrl, ...]:
        if mime_data.hasUrls():
            return tuple(url for url in mime_data.urls() if url.isLocalFile())

        raw_uris = mime_data.data("text/uri-list")
        if not raw_uris:
            return ()

        lines = bytes(raw_uris.data()).splitlines()
        urls: list[QUrl] = []
        for line in lines:
            text = line.decode().strip()
            if not text or text.startswith("#"):
                continue
            url = QUrl(text)
            if url.isValid() and url.isLocalFile():
                urls.append(url)

        return tuple(urls)

    def _selected_entry(self) -> tuple[CatalogEntry, int] | None:
        selection_model = self._view.selectionModel()
        if selection_model is None:
            return None

        current_index = selection_model.currentIndex()
        if not current_index.isValid():
            return None

        row = current_index.row()
        if row < 0 or row >= self._model.rowCount():
            return None

        return self._model.entry_at(row), row

    def _selected_entries(self) -> tuple[tuple[CatalogEntry, int], ...]:
        """Return every selected dataset in view row order, de-duplicated by row."""
        selection_model = self._view.selectionModel()
        if selection_model is None:
            return ()
        row_count = self._model.rowCount()
        rows = sorted(
            {
                index.row()
                for index in selection_model.selectedIndexes()
                if 0 <= index.row() < row_count
            }
        )
        return tuple((self._model.entry_at(row), row) for row in rows)

    def _resolve_context_target(self, position: QPoint) -> tuple[CatalogEntry, int] | None:
        """Anchor the context menu on the right-clicked row.

        A blank-space click must not inherit a stale ``currentIndex()``, so it resolves to
        ``None`` rather than deferring to :meth:`_selected_entry`.
        """
        index = self._view.indexAt(position)
        if not index.isValid():
            return None
        selection_model = self._view.selectionModel()
        if selection_model is None:
            return None
        # SelectItems means a selected row may have no selected cell in the clicked column,
        # so test row membership, not cell membership.
        already_selected = selection_model.rowIntersectsSelection(index.row())
        selection_model.setCurrentIndex(
            index,
            QItemSelectionModel.SelectionFlag.NoUpdate
            if already_selected
            else QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        return self._selected_entry()

    def _on_context_menu(self, position: QPoint) -> None:
        target = self._resolve_context_target(position)
        selected = self._selected_entries() if target is not None else ()
        has_any = bool(selected)
        single = len(selected) == 1
        one_folder = len({entry.path.parent for entry, _ in selected}) == 1
        menu = QMenu(self)

        self._rename_action.setEnabled(single)
        self._remove_action.setEnabled(has_any)
        self._refresh_action.setEnabled(has_any)
        self._copy_alias_action.setEnabled(has_any)
        self._copy_path_action.setEnabled(has_any)
        self._insert_alias_action.setEnabled(has_any)
        self._reveal_action.setEnabled(has_any and one_folder)

        menu.addAction(self._rename_action)
        menu.addAction(self._remove_action)
        menu.addAction(self._refresh_action)
        menu.addSeparator()
        menu.addAction(self._copy_alias_action)
        menu.addAction(self._copy_path_action)
        menu.addAction(self._reveal_action)
        menu.addSeparator()
        menu.addAction(self._insert_alias_action)

        viewport = self._view.viewport()
        if viewport is None:
            return
        menu.popup(viewport.mapToGlobal(position))

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
        selected = self._selected_entries()
        if not selected:
            return

        self._catalog_service.remove_many(entry.id for entry, _ in selected)

    def _refresh_schema(self) -> None:
        selected = self._selected_entries()
        if not selected:
            return

        for entry, _ in selected:
            self.refresh_schema_requested.emit(
                CatalogBinding(
                    entry_id=entry.id,
                    alias=entry.alias,
                    path=entry.path,
                    source_format=entry.source_format,
                )
            )

    def _copy_alias(self) -> None:
        selected = self._selected_entries()
        if not selected:
            return

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText("\n".join(entry.alias for entry, _ in selected))

    def _copy_path(self) -> None:
        selected = self._selected_entries()
        if not selected:
            return

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText("\n".join(str(entry.path) for entry, _ in selected))

    @staticmethod
    def reveal_command(path: Path) -> list[str]:
        """Return the platform-native command without launching it."""
        if sys.platform == "darwin":
            return ["open", "-R", str(path)]
        if sys.platform == "win32":
            return ["explorer", "/select,", str(path)]
        return ["xdg-open", str(path if path.is_dir() else path.parent)]

    def _reveal_selected(self) -> None:
        selected = self._selected_entries()
        folders = {entry.path.parent for entry, _ in selected}
        if len(folders) != 1:
            return
        target = folders.pop()
        subprocess.Popen(self.reveal_command(target))  # fixed platform command

    def _insert_alias(self) -> None:
        selected = self._selected_entries()
        if not selected:
            return

        self.insert_alias_requested.emit(", ".join(entry.alias for entry, _ in selected))
