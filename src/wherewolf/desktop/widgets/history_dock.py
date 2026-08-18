"""History table widget backed by stable history-record IDs."""

from __future__ import annotations

from datetime import UTC, datetime

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wherewolf.storage.history import HistoryManager


class HistoryItem(QTreeWidgetItem):
    """History row that orders timestamps by their actual instant."""

    def __init__(self, labels: list[str], raw_timestamp: str, pinned: bool) -> None:
        super().__init__(labels)
        self._pinned = pinned
        try:
            parsed = datetime.fromisoformat(raw_timestamp)
            self._timestamp = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError:
            self._timestamp = None

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        tree = self.treeWidget()
        if tree is not None and isinstance(other, HistoryItem) and self._pinned != other._pinned:
            header = tree.header()
            if header is not None and header.sortIndicatorOrder() is Qt.SortOrder.DescendingOrder:
                return not self._pinned
            return self._pinned
        if (
            tree is not None
            and tree.sortColumn() == 0
            and isinstance(other, HistoryItem)
            and self._timestamp is not None
            and other._timestamp is not None
        ):
            return self._timestamp < other._timestamp
        return super().__lt__(other)


class HistoryDock(QWidget):
    """Display persisted query history and emit the record selected by UUID."""

    record_selected = pyqtSignal(dict)
    history_records_selected = pyqtSignal(list)

    def __init__(self, history_manager: HistoryManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_manager = history_manager
        self.history_filter = QLineEdit(self)
        self.history_filter.setObjectName("history_filter")
        self.history_filter.setPlaceholderText("Filter history")
        self.history_filter.textChanged.connect(self._apply_filter)
        self.history_table = QTreeWidget(self)
        self.history_table.setObjectName("history_table")
        self.history_table.setColumnCount(2)
        self.history_table.setHeaderLabels(["Timestamp", "Query"])
        self.history_table.setAlternatingRowColors(True)
        header = self.history_table.header()
        if header is not None:
            header.setSectionsMovable(True)
            header.setFirstSectionMovable(True)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(0, 240)
            header.setStretchLastSection(True)
            header.setSortIndicatorShown(True)
            header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        self.history_table.setSortingEnabled(True)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_table.itemActivated.connect(self._on_item_activated)
        self.history_table.customContextMenuRequested.connect(self._on_context_menu)

        self._delete_action = QAction("Delete", self)
        self._delete_action.triggered.connect(self._delete_selected_records)
        self._save_as_sql_action = QAction("Save as SQL…", self)
        self._save_as_sql_action.triggered.connect(self._save_selected_records_as_sql)
        self._pin_action = QAction("Pin", self)
        self._pin_action.triggered.connect(self._toggle_selected_record_pins)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.history_filter)
        layout.addWidget(self.history_table)
        self.refresh()

    def refresh(self) -> None:
        """Reload the visible list from disk while retaining UUIDs in item data."""
        self.history_table.clear()
        for record in self._history_manager.get_all():
            query = str(record["query"]).replace("\n", " ")
            truncated = query[:80] + ("…" if len(query) > 80 else "")
            pinned = bool(record["pinned"])
            if pinned:
                truncated = f"📌 {truncated}"
            raw_timestamp = str(record["timestamp"])
            try:
                timestamp = datetime.fromisoformat(raw_timestamp).replace(microsecond=0).isoformat()
            except ValueError:
                timestamp = raw_timestamp
            item = HistoryItem([timestamp, truncated], raw_timestamp, pinned)
            item.setData(0, Qt.ItemDataRole.UserRole, record["id"])
            item.setToolTip(0, raw_timestamp)
            item.setToolTip(1, str(record["query"]))
            self.history_table.addTopLevelItem(item)
        self._apply_filter()

    def _apply_filter(self) -> None:
        filter_text = self.history_filter.text().casefold()
        for row in range(self.history_table.topLevelItemCount()):
            item = self.history_table.topLevelItem(row)
            if item is not None:
                item.setHidden(filter_text not in item.toolTip(1).casefold())

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(entry_id, str):
            return
        record = self._history_manager.get_by_id(entry_id)
        if record is not None:
            self.record_selected.emit(record)

    def _on_context_menu(self, position: QPoint) -> None:
        item = self.history_table.itemAt(position)
        if item is not None and not item.isSelected():
            self.history_table.clearSelection()
            item.setSelected(True)
            self.history_table.setCurrentItem(item)

        has_selected_records = bool(self._selected_record_ids())
        self._delete_action.setEnabled(has_selected_records)
        self._save_as_sql_action.setEnabled(has_selected_records)
        self._pin_action.setEnabled(has_selected_records)
        self._pin_action.setText("Unpin" if self._selected_records_are_pinned() else "Pin")
        menu = QMenu(self)
        menu.addAction(self._pin_action)
        menu.addAction(self._save_as_sql_action)
        menu.addAction(self._delete_action)

        viewport = self.history_table.viewport()
        if viewport is not None:
            menu.popup(viewport.mapToGlobal(position))

    def _selected_record_ids(self) -> list[str]:
        record_ids: list[str] = []
        for item in self.history_table.selectedItems():
            record_id = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(record_id, str):
                record_ids.append(record_id)
        return record_ids

    def _selected_records_are_pinned(self) -> bool:
        record_ids = self._selected_record_ids()
        return bool(record_ids) and all(
            bool(record["pinned"])
            for record_id in record_ids
            if (record := self._history_manager.get_by_id(record_id)) is not None
        )

    def _toggle_selected_record_pins(self) -> None:
        record_ids = self._selected_record_ids()
        if not record_ids:
            return
        pinned = not self._selected_records_are_pinned()
        for record_id in record_ids:
            self._history_manager.set_pinned(record_id, pinned)
        self.refresh()

    def _delete_selected_records(self) -> None:
        record_ids = self._selected_record_ids()
        record_count = len(record_ids)
        if record_count == 0:
            return

        record_label = "record" if record_count == 1 else "records"
        result = QMessageBox.question(
            self,
            "Delete History",
            f"Delete {record_count} history {record_label}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result is not QMessageBox.StandardButton.Yes:
            return

        self._history_manager.delete_records(record_ids)
        self.refresh()

    def _save_selected_records_as_sql(self) -> None:
        selected_records = [
            record
            for record_id in self._selected_record_ids()
            if (record := self._history_manager.get_by_id(record_id)) is not None
        ]
        if selected_records:
            self.history_records_selected.emit(selected_records)
