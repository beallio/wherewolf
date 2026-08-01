"""Qt QTableView for displaying query result DataFrames."""

from __future__ import annotations

import polars as pl
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QMenu, QTableView

from wherewolf.desktop.clipboard_serializers import format_cell_value, format_header_name
from wherewolf.desktop.models.polars_table_model import PolarsTableModel
from wherewolf.desktop.models.typed_sort_proxy_model import TypedSortProxyModel


class ResultTableView(QTableView):
    """QTableView configured for polars query results with type-aware sorting and copy."""

    insert_header_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_model = PolarsTableModel(parent=self)
        self._proxy_model = TypedSortProxyModel(parent=self)
        self._proxy_model.setSourceModel(self._source_model)

        self.setModel(self._proxy_model)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSectionsMovable(True)
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(
            self._on_header_context_menu_requested
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def proxy_model(self) -> TypedSortProxyModel:
        return self._proxy_model

    def source_model(self) -> PolarsTableModel:
        return self._source_model

    def set_frame(self, frame: pl.DataFrame | None) -> None:
        self._source_model.set_frame(frame)
        self._proxy_model.sort(-1, Qt.SortOrder.AscendingOrder)

    def frame(self) -> pl.DataFrame:
        return self._source_model.frame()

    def create_header_context_menu(self, column: int) -> QMenu:
        menu = QMenu(self)
        h_name = str(
            self._proxy_model.headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            or ""
        )

        menu.addAction(
            "Sort Ascending",
            lambda: self.proxy_model().sort(column, Qt.SortOrder.AscendingOrder),
        )
        menu.addAction(
            "Sort Descending",
            lambda: self.proxy_model().sort(column, Qt.SortOrder.DescendingOrder),
        )
        menu.addAction(
            "Clear Sort",
            lambda: self.proxy_model().sort(-1, Qt.SortOrder.AscendingOrder),
        )
        menu.addSeparator()
        menu.addAction(
            "Copy Header Name",
            lambda: QApplication.clipboard().setText(h_name),
        )
        menu.addAction(
            "Copy Quoted Header",
            lambda: QApplication.clipboard().setText(format_header_name(h_name, quote=True)),
        )
        menu.addSeparator()
        menu.addAction(
            "Insert Header into Editor",
            lambda: self.insert_header_requested.emit(h_name),
        )
        return menu

    def _on_header_context_menu_requested(self, pos: QPoint) -> None:
        column = self.horizontalHeader().logicalIndexAt(pos)
        if column >= 0:
            menu = self.create_header_context_menu(column)
            menu.exec(self.horizontalHeader().mapToGlobal(pos))

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
            event.accept()
        else:
            super().keyPressEvent(event)

    def copy_selection(self, include_headers: bool = False, quote_headers: bool = False) -> None:
        selected_indexes = self.selectionModel().selectedIndexes()
        if not selected_indexes or self._proxy_model.rowCount() == 0:
            return

        header = self.horizontalHeader()

        selected_cells: list[tuple[int, int]] = []
        for idx in selected_indexes:
            if idx.isValid():
                p_row = idx.row()
                p_col = idx.column()
                if not header.isSectionHidden(p_col):
                    v_col = header.visualIndex(p_col)
                    selected_cells.append((p_row, v_col))

        if not selected_cells:
            return

        sorted_cells = sorted(set(selected_cells), key=lambda x: (x[0], x[1]))
        used_visual_cols = sorted({v_col for _, v_col in sorted_cells})

        num_cols = self._proxy_model.columnCount()
        v_to_p: dict[int, int] = {}
        for p_col in range(num_cols):
            v_col = header.visualIndex(p_col)
            v_to_p[v_col] = p_col

        rows_dict: dict[int, list[int]] = {}
        for p_row, v_col in sorted_cells:
            if p_row not in rows_dict:
                rows_dict[p_row] = []
            rows_dict[p_row].append(v_col)

        lines = []
        if include_headers:
            header_parts = []
            for v_col in used_visual_cols:
                p_col = v_to_p[v_col]
                h_name = str(
                    self._proxy_model.headerData(
                        p_col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
                    )
                    or ""
                )
                header_parts.append(format_header_name(h_name, quote=quote_headers))
            lines.append("\t".join(header_parts))

        for p_row in sorted(rows_dict.keys()):
            v_cols = rows_dict[p_row]
            row_parts = []
            for v_col in v_cols:
                p_col = v_to_p[v_col]
                val = self._proxy_model.data(
                    self._proxy_model.index(p_row, p_col), Qt.ItemDataRole.UserRole
                )
                row_parts.append(format_cell_value(val))
            lines.append("\t".join(row_parts))

        tsv_text = "\n".join(lines)
        if tsv_text:
            QApplication.clipboard().setText(tsv_text)
