"""Qt table model backed by a Polars DataFrame."""

from __future__ import annotations

import polars as pl
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

NULL_PLACEHOLDER = "<null>"


class PolarsTableModel(QAbstractTableModel):
    """QAbstractTableModel facade over a polars DataFrame."""

    _INVALID_PARENT: QModelIndex = QModelIndex()

    def __init__(
        self, frame: pl.DataFrame | None = None, parent=None, *, row_offset: int = 0
    ) -> None:
        super().__init__(parent)
        if row_offset < 0:
            raise ValueError("Row offset cannot be negative")
        self._frame = frame if frame is not None else pl.DataFrame()
        self._row_offset = row_offset
        self._header_badges: list[str] = []

    def set_frame(self, frame: pl.DataFrame | None, *, row_offset: int = 0) -> None:
        if row_offset < 0:
            raise ValueError("Row offset cannot be negative")
        self.beginResetModel()
        self._frame = frame if frame is not None else pl.DataFrame()
        self._row_offset = row_offset
        self._header_badges = [""] * self._frame.width
        self.endResetModel()

    def set_header_badges(self, badges: list[str]) -> None:
        """Set readable runtime-generated result header badges for the current frame."""
        self._header_badges = [*badges]
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
            column_name = self._frame.columns[section]
            if role == Qt.ItemDataRole.DisplayRole:
                if section < len(self._header_badges) and self._header_badges[section]:
                    return f"{column_name} [{self._header_badges[section]}]"
                return column_name
            if role == Qt.ItemDataRole.ToolTipRole:
                return f"{column_name}: {self._frame.dtypes[section]}"
            if role == Qt.ItemDataRole.UserRole and section < len(self._header_badges):
                return self._header_badges[section]
        if (
            orientation == Qt.Orientation.Vertical
            and 0 <= section < self._frame.height
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return section + self._row_offset + 1
        return None
