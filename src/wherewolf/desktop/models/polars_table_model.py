"""Qt table model backed by a Polars DataFrame."""

from __future__ import annotations

import polars as pl
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class PolarsTableModel(QAbstractTableModel):
    """QAbstractTableModel facade over a polars DataFrame."""

    _INVALID_PARENT: QModelIndex = QModelIndex()

    def __init__(self, frame: pl.DataFrame | None = None, parent=None) -> None:
        super().__init__(parent)
        self._frame = frame if frame is not None else pl.DataFrame()

    def set_frame(self, frame: pl.DataFrame | None) -> None:
        self.beginResetModel()
        self._frame = frame if frame is not None else pl.DataFrame()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = self._INVALID_PARENT
        if parent.isValid():
            return 0
        return self._frame.height

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = self._INVALID_PARENT
        if parent.isValid():
            return 0
        return self._frame.width

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        if not (0 <= row < self._frame.height and 0 <= col < self._frame.width):
            return None

        val = self._frame[row, col]

        if role == Qt.ItemDataRole.DisplayRole:
            if val is None:
                return "null"  # Placeholder, will be refined in Task 3
            return str(val)

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < self._frame.width:
            return self._frame.columns[section]
        if orientation == Qt.Orientation.Vertical and 0 <= section < self._frame.height:
            return section + 1
        return None
