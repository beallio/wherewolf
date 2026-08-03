"""Type-aware QSortFilterProxyModel for sorting result grid data."""

from __future__ import annotations

import re

import duckdb
from PyQt6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)

from wherewolf.desktop.models.polars_table_model import PolarsTableModel

_PREDICATE_MARKERS = re.compile(
    r"(?:[<>=!]\s*=?|\b(?:AND|OR|NOT|IN|LIKE|IS|BETWEEN)\b)", re.IGNORECASE
)


class TypedSortProxyModel(QSortFilterProxyModel):
    """Sort proxy model comparing typed values from Qt.ItemDataRole.UserRole."""

    filter_error_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_sort_column: int = -1
        self._current_sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
        self._filter_text: str = ""
        self._active_filter_text: str = ""
        self._active_expression_rows: set[int] | None = None
        self._filter_error: str = ""

    def setSourceModel(self, sourceModel: QAbstractItemModel | None) -> None:
        super().setSourceModel(sourceModel)
        if sourceModel is not None:
            sourceModel.modelReset.connect(self._reapply_filter)

    def current_sort_column(self) -> int:
        return self._current_sort_column

    def current_sort_order(self) -> Qt.SortOrder:
        return self._current_sort_order

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text.strip()
        if not self._filter_text:
            self._active_filter_text = ""
            self._active_expression_rows = None
            self._set_filter_error("")
            self.invalidateFilter()
            return

        try:
            rows = self._evaluate_predicate(self._filter_text)
        except Exception as exc:  # noqa: BLE001  # User-entered filter boundary
            if _PREDICATE_MARKERS.search(self._filter_text):
                self._set_filter_error(f"Filter error for '{self._filter_text}': {exc}")
                return
            self._active_filter_text = self._filter_text.lower()
            self._active_expression_rows = None
        else:
            self._active_filter_text = ""
            self._active_expression_rows = rows
            self._set_filter_error("")
        self.invalidateFilter()

    def _evaluate_predicate(self, expression: str) -> set[int]:
        source_model = self.sourceModel()
        if not isinstance(source_model, PolarsTableModel):
            return set()
        frame = source_model.frame()
        marker = "__wherewolf_filter_row"
        while marker in frame.columns:
            marker = f"_{marker}"
        indexed_frame = frame.with_row_index(marker)
        connection = duckdb.connect(database=":memory:")
        try:
            connection.register("frame", indexed_frame)
            rows = connection.execute(f'SELECT "{marker}" FROM frame WHERE {expression}').fetchall()
            return {int(row[0]) for row in rows}
        finally:
            connection.close()

    def _reapply_filter(self) -> None:
        if self._filter_text:
            self.set_filter_text(self._filter_text)

    def _set_filter_error(self, message: str) -> None:
        if message == self._filter_error:
            return
        self._filter_error = message
        self.filter_error_changed.emit(message)

    def filter_text(self) -> str:
        return self._filter_text

    def toggle_sort(self, column: int) -> None:
        """Cycle column sort through Ascending -> Descending -> Unsorted."""
        if column != self._current_sort_column:
            self._current_sort_column = column
            self._current_sort_order = Qt.SortOrder.AscendingOrder
            self.sort(column, Qt.SortOrder.AscendingOrder)
        else:
            if self._current_sort_order == Qt.SortOrder.AscendingOrder:
                self._current_sort_order = Qt.SortOrder.DescendingOrder
                self.sort(column, Qt.SortOrder.DescendingOrder)
            elif self._current_sort_order == Qt.SortOrder.DescendingOrder:
                self._current_sort_column = -1
                self._current_sort_order = Qt.SortOrder.AscendingOrder
                self.sort(-1, Qt.SortOrder.AscendingOrder)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._active_expression_rows is not None:
            return source_row in self._active_expression_rows
        if not self._active_filter_text:
            return True
        source_model = self.sourceModel()
        if source_model is None:
            return True
        num_cols = source_model.columnCount(source_parent)
        for col in range(num_cols):
            idx = source_model.index(source_row, col, source_parent)
            val = source_model.data(idx, Qt.ItemDataRole.DisplayRole)
            if val is not None and self._active_filter_text in str(val).lower():
                return True
        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False

        left_val = model.data(left, Qt.ItemDataRole.UserRole)
        right_val = model.data(right, Qt.ItemDataRole.UserRole)

        if left_val is None and right_val is None:
            return False

        # Null ordering: nulls last on both ascending and descending
        if left_val is None:
            return self.sortOrder() == Qt.SortOrder.DescendingOrder
        if right_val is None:
            return self.sortOrder() == Qt.SortOrder.AscendingOrder

        try:
            return left_val < right_val
        except TypeError:
            return str(left_val) < str(right_val)
