"""History table widget backed by stable history-record IDs."""

from __future__ import annotations

from datetime import UTC, datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from wherewolf.storage.history import HistoryManager


class HistoryItem(QTreeWidgetItem):
    """History row that orders timestamps by their actual instant."""

    def __init__(self, labels: list[str], raw_timestamp: str) -> None:
        super().__init__(labels)
        try:
            parsed = datetime.fromisoformat(raw_timestamp)
            self._timestamp = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError:
            self._timestamp = None

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        tree = self.treeWidget()
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

    def __init__(self, history_manager: HistoryManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_manager = history_manager
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
        self.history_table.itemActivated.connect(self._on_item_activated)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.history_table)
        self.refresh()

    def refresh(self) -> None:
        """Reload the visible list from disk while retaining UUIDs in item data."""
        self.history_table.clear()
        for record in self._history_manager.get_all():
            query = str(record["query"]).replace("\n", " ")
            truncated = query[:80] + ("…" if len(query) > 80 else "")
            raw_timestamp = str(record["timestamp"])
            try:
                timestamp = datetime.fromisoformat(raw_timestamp).replace(microsecond=0).isoformat()
            except ValueError:
                timestamp = raw_timestamp
            item = HistoryItem([timestamp, truncated], raw_timestamp)
            item.setData(0, Qt.ItemDataRole.UserRole, record["id"])
            item.setToolTip(0, raw_timestamp)
            item.setToolTip(1, str(record["query"]))
            self.history_table.addTopLevelItem(item)

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(entry_id, str):
            return
        record = self._history_manager.get_by_id(entry_id)
        if record is not None:
            self.record_selected.emit(record)
