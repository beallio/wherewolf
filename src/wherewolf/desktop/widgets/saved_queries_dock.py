"""Dock content for browsing and acting on named SQL queries."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from wherewolf.storage.saved_queries import SavedQuery, SavedQueryStore


class SavedQueriesDock(QWidget):
    """Filter saved queries and emit the selected record for window-level actions."""

    run_requested = pyqtSignal(object)
    open_in_new_tab_requested = pyqtSignal(object)
    rename_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)

    def __init__(self, saved_query_store: SavedQueryStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._saved_query_store = saved_query_store
        self.query_filter = QLineEdit(self)
        self.query_filter.setObjectName("saved_queries_filter")
        self.query_filter.setPlaceholderText("Filter saved queries")
        self.query_filter.textChanged.connect(self._apply_filter)
        self.query_list = QListWidget(self)
        self.query_list.setObjectName("saved_queries_list")
        self.query_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.query_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.query_list.customContextMenuRequested.connect(self._on_context_menu)
        self.query_list.itemActivated.connect(lambda _item: self._emit_selected(self.run_requested))

        self._run_action = QAction("Run", self)
        self._open_in_new_tab_action = QAction("Open in New Tab", self)
        self._rename_action = QAction("Rename", self)
        self._delete_action = QAction("Delete", self)
        self._run_action.triggered.connect(lambda: self._emit_selected(self.run_requested))
        self._open_in_new_tab_action.triggered.connect(
            lambda: self._emit_selected(self.open_in_new_tab_requested)
        )
        self._rename_action.triggered.connect(lambda: self._emit_selected(self.rename_requested))
        self._delete_action.triggered.connect(lambda: self._emit_selected(self.delete_requested))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.query_filter)
        layout.addWidget(self.query_list)
        self.refresh()

    def refresh(self) -> None:
        """Reload records from the store and retain stable IDs on list items."""
        self.query_list.clear()
        for query in self._saved_query_store.get_all():
            item = QListWidgetItem(query.name)
            item.setData(Qt.ItemDataRole.UserRole, query.id)
            item.setToolTip(query.description or query.sql)
            self.query_list.addItem(item)
        self._apply_filter(self.query_filter.text())

    def _apply_filter(self, filter_text: str) -> None:
        needle = filter_text.casefold()
        for index in range(self.query_list.count()):
            item = self.query_list.item(index)
            if item is None:
                continue
            query = self._query_for_item(item)
            if query is not None:
                searchable = f"{query.name}\n{query.description}\n{query.sql}".casefold()
                item.setHidden(needle not in searchable)

    def _on_context_menu(self, position: QPoint) -> None:
        item = self.query_list.itemAt(position)
        if item is not None:
            self.query_list.setCurrentItem(item)
        has_selection = self._selected_query() is not None
        for action in (
            self._run_action,
            self._open_in_new_tab_action,
            self._rename_action,
            self._delete_action,
        ):
            action.setEnabled(has_selection)
        menu = QMenu(self)
        menu.addAction(self._run_action)
        menu.addAction(self._open_in_new_tab_action)
        menu.addSeparator()
        menu.addAction(self._rename_action)
        menu.addAction(self._delete_action)
        viewport = self.query_list.viewport()
        if viewport is not None:
            menu.popup(viewport.mapToGlobal(position))

    def _selected_query(self) -> SavedQuery | None:
        return self._query_for_item(self.query_list.currentItem())

    def _query_for_item(self, item: QListWidgetItem | None) -> SavedQuery | None:
        if item is None:
            return None
        query_id = item.data(Qt.ItemDataRole.UserRole)
        return self._saved_query_store.get_by_id(query_id) if isinstance(query_id, str) else None

    def _emit_selected(self, signal) -> None:
        query = self._selected_query()
        if query is not None:
            signal.emit(query)
