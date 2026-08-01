"""Type-aware QSortFilterProxyModel for sorting result grid data."""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, QSortFilterProxyModel, Qt


class TypedSortProxyModel(QSortFilterProxyModel):
    """Sort proxy model comparing typed values from Qt.ItemDataRole.UserRole."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_sort_column: int = -1
        self._current_sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
        self._filter_text: str = ""

    def current_sort_column(self) -> int:
        return self._current_sort_column

    def current_sort_order(self) -> Qt.SortOrder:
        return self._current_sort_order

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text.strip().lower()
        self.invalidateFilter()

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
        if not self._filter_text:
            return True
        source_model = self.sourceModel()
        if source_model is None:
            return True
        num_cols = source_model.columnCount(source_parent)
        for col in range(num_cols):
            idx = source_model.index(source_row, col, source_parent)
            val = source_model.data(idx, Qt.ItemDataRole.DisplayRole)
            if val is not None and self._filter_text in str(val).lower():
                return True
        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_val = self.sourceModel().data(left, Qt.ItemDataRole.UserRole)
        right_val = self.sourceModel().data(right, Qt.ItemDataRole.UserRole)

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
