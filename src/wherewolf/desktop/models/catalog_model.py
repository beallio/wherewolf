"""Model objects for the dataset catalog table."""

from __future__ import annotations

from typing import ClassVar

from PyQt6.QtCore import (
    QAbstractTableModel,
    QMetaObject,
    QModelIndex,
    Qt,
    QThread,
    pyqtSignal,
    pyqtSlot,
)

from wherewolf.domain import CatalogEntry
from wherewolf.services import CatalogService


class CatalogModel(QAbstractTableModel):
    """QAbstractTableModel facade over :class:`CatalogService`."""

    _INVALID_PARENT: QModelIndex = QModelIndex()
    _COLUMNS: ClassVar[tuple[str, str, str, str]] = (
        "Alias",
        "File",
        "Format",
        "Schema status",
    )

    class SchemaStatus:
        LOADING = "Loading"
        READY = "Ready"
        ERROR = "Error"

    rename_failed = pyqtSignal(str)

    def __init__(self, catalog_service: CatalogService, parent=None) -> None:
        super().__init__(parent)
        self._catalog_service = catalog_service
        self._entries = tuple(catalog_service.entries)
        self._catalog_service.subscribe(self._on_catalog_changed)

    @staticmethod
    def headers() -> tuple[str, ...]:
        return CatalogModel._COLUMNS

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = self._INVALID_PARENT
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = self._INVALID_PARENT
        if parent.isValid():
            return 0
        return len(self._COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        entry = self._entries[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if index.column() == 0:
                return entry.alias
            if index.column() == 1:
                return str(entry.path)
            if index.column() == 2:
                return entry.source_format.value
            if index.column() == 3:
                return self._schema_status_text(entry)
            return None

        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 1:
            return str(entry.path)

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._COLUMNS):
            return self._COLUMNS[section]
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def flags(self, index: QModelIndex):
        base_flags = super().flags(index)
        if index.column() == 0:
            return base_flags | Qt.ItemFlag.ItemIsEditable
        return base_flags

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or index.column() != 0:
            return False

        entry = self._entries[index.row()]
        alias = str(value)
        try:
            self._catalog_service.rename(entry.id, alias)
        except ValueError as err:
            self.rename_failed.emit(str(err))
            return False
        return True

    def entry_at(self, row: int) -> CatalogEntry:
        return self._entries[row]

    @pyqtSlot()
    def _on_catalog_changed(self) -> None:
        if QThread.currentThread() is not self.thread():
            QMetaObject.invokeMethod(
                self,
                "_on_catalog_changed",
                Qt.ConnectionType.QueuedConnection,
            )
            return

        new_entries = tuple(self._catalog_service.entries)
        if new_entries == self._entries:
            return

        self.beginResetModel()
        self._entries = new_entries
        self.endResetModel()

    def _schema_status_text(self, entry: CatalogEntry) -> str:
        if entry.schema_error:
            return f"Error: {entry.schema_error}"
        if entry.schema is None:
            return self.SchemaStatus.LOADING
        return self.SchemaStatus.READY
