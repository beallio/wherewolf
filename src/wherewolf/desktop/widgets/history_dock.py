"""History list widget backed by stable history-record IDs."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from wherewolf.storage.history import HistoryManager


class HistoryDock(QWidget):
    """Display persisted query history and emit the record selected by UUID."""

    record_selected = pyqtSignal(dict)

    def __init__(self, history_manager: HistoryManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history_manager = history_manager
        self.history_list = QListWidget(self)
        self.history_list.setObjectName("history_list")
        self.history_list.itemActivated.connect(self._on_item_activated)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.history_list)
        self.refresh()

    def refresh(self) -> None:
        """Reload the visible list from disk while retaining UUIDs in item data."""
        self.history_list.clear()
        for record in self._history_manager.get_all():
            item = QListWidgetItem(self._label_for(record), self.history_list)
            item.setData(Qt.ItemDataRole.UserRole, record["id"])

    @staticmethod
    def _label_for(record: dict) -> str:
        return f"{record['timestamp'][:16]} - {record['query'][:30]}..."

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry_id, str):
            return
        record = self._history_manager.get_by_id(entry_id)
        if record is not None:
            self.record_selected.emit(record)
