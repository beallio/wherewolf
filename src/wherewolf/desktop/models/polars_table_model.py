"""Qt table model backed by a Polars DataFrame."""

from __future__ import annotations

import polars as pl
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QIcon

NULL_PLACEHOLDER = "<null>"


class PolarsTableModel(QAbstractTableModel):
    """QAbstractTableModel facade over a polars DataFrame."""

    _INVALID_PARENT: QModelIndex = QModelIndex()

    def __init__(self, frame: pl.DataFrame | None = None, parent=None) -> None:
        super().__init__(parent)
        self._frame = frame if frame is not None else pl.DataFrame()
        self._header_icons: list[QIcon | None] = []

    def set_frame(self, frame: pl.DataFrame | None) -> None:
        self.beginResetModel()
        self._frame = frame if frame is not None else pl.DataFrame()
        self._header_icons = [None] * self._frame.width
        self.endResetModel()

    def set_header_icons(self, icons: list[QIcon]) -> None:
        """Set runtime-generated result header icons for the current frame."""
        self._header_icons = [*icons]
        if self._frame.width:
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, self._frame.width - 1)

    def frame(self) -> pl.DataFrame:
        return self._frame

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

        if role == Qt.ItemDataRole.UserRole:
            return val

        if role == Qt.ItemDataRole.DisplayRole:
            if val is None:
                return NULL_PLACEHOLDER
            return str(val)

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < self._frame.width:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._frame.columns[section]
            if role == Qt.ItemDataRole.ToolTipRole:
                return f"{self._frame.columns[section]}: {self._frame.dtypes[section]}"
            if role == Qt.ItemDataRole.DecorationRole and section < len(self._header_icons):
                return self._header_icons[section]
        if (
            orientation == Qt.Orientation.Vertical
            and 0 <= section < self._frame.height
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return section + 1
        return None
