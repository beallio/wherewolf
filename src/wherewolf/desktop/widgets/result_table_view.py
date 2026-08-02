"""Qt QTableView for displaying query result DataFrames."""

from __future__ import annotations

import polars as pl
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QApplication, QMenu, QTableView

from wherewolf.desktop.clipboard_serializers import format_cell_value, format_header_name
from wherewolf.desktop.models.polars_table_model import PolarsTableModel
from wherewolf.desktop.models.typed_sort_proxy_model import TypedSortProxyModel


class ResultTableView(QTableView):
    """QTableView configured for polars query results with type-aware sorting and copy."""

    insert_header_requested = pyqtSignal(str)
    apply_query_order_requested = pyqtSignal(str, str)
    local_sort_changed = pyqtSignal(bool)
    frame_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_model = PolarsTableModel(parent=self)
        self._proxy_model = TypedSortProxyModel(parent=self)
        self._proxy_model.setSourceModel(self._source_model)

        self.setModel(self._proxy_model)
        self.setSortingEnabled(True)
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionsMovable(True)
            header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            header.customContextMenuRequested.connect(self._on_header_context_menu_requested)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_body_context_menu_requested)

    def proxy_model(self) -> TypedSortProxyModel:
        return self._proxy_model

    def source_model(self) -> PolarsTableModel:
        return self._source_model

    def set_frame(self, frame: pl.DataFrame | None) -> None:
        self._source_model.set_frame(frame)
        self._proxy_model.sort(-1, Qt.SortOrder.AscendingOrder)
        self.local_sort_changed.emit(False)
        self.frame_changed.emit(self.has_result())

    def frame(self) -> pl.DataFrame:
        return self._source_model.frame()

    def selection_for_export(self) -> tuple[list[tuple[int, int]], list[int]]:
        """Return selected source cells and the displayed visual column order."""
        selection_model = self.selectionModel()
        header = self.horizontalHeader()
        if selection_model is None or header is None:
            return [], []
        column_order = [
            logical
            for _visual, logical in sorted(
                (header.visualIndex(logical), logical)
                for logical in range(self._proxy_model.columnCount())
                if not self.isColumnHidden(logical)
            )
        ]
        selected_cells: list[tuple[int, int]] = []
        for index in selection_model.selectedIndexes():
            if not index.isValid() or self.isColumnHidden(index.column()):
                continue
            source_index = self._proxy_model.mapToSource(index)
            if source_index.isValid():
                selected_cells.append((source_index.row(), header.visualIndex(index.column())))
        return selected_cells, column_order

    def has_result(self) -> bool:
        df = self._source_model.frame()
        return bool(df is not None and not df.is_empty())

    def move_column(self, from_visual: int, to_visual: int) -> None:
        header = self.horizontalHeader()
        if header is not None:
            header.moveSection(from_visual, to_visual)

    def hide_column(self, column: int) -> None:
        self.setColumnHidden(column, True)

    def show_column(self, column: int) -> None:
        self.setColumnHidden(column, False)

    def show_all_columns(self) -> None:
        for c in range(self._proxy_model.columnCount()):
            self.setColumnHidden(c, False)

    def auto_size_columns(self) -> None:
        self.resizeColumnsToContents()

    def sortByColumn(self, column: int, order: Qt.SortOrder) -> None:
        """Sort the in-memory preview and disclose when query order is unchanged."""
        self._proxy_model.sort(column, order)
        self.local_sort_changed.emit(column >= 0)

    def _sort_locally(self, column: int, order: Qt.SortOrder) -> None:
        self.sortByColumn(column, order)

    def reset_columns_default(self) -> None:
        header = self.horizontalHeader()
        if header is None:
            return
        num_cols = self._proxy_model.columnCount()
        for c in range(num_cols):
            self.setColumnHidden(c, False)
            v_idx = header.visualIndex(c)
            if v_idx != c:
                header.moveSection(v_idx, c)

    def _set_clipboard_text(self, text: str) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)

    def copy_all_visible_column_names(self) -> None:
        """Copy the visible headers in their current left-to-right order."""
        header = self.horizontalHeader()
        if header is None:
            return
        columns = sorted(
            (
                (header.visualIndex(column), column)
                for column in range(self._proxy_model.columnCount())
                if not self.isColumnHidden(column)
            ),
            key=lambda pair: pair[0],
        )
        names = [
            str(
                self._proxy_model.headerData(
                    column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
                )
                or ""
            )
            for _visual_index, column in columns
        ]
        self._set_clipboard_text("\t".join(names))

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
            lambda: self._sort_locally(column, Qt.SortOrder.AscendingOrder),
        )
        menu.addAction(
            "Sort Descending",
            lambda: self._sort_locally(column, Qt.SortOrder.DescendingOrder),
        )
        menu.addAction(
            "Clear Sort",
            lambda: self._sort_locally(-1, Qt.SortOrder.AscendingOrder),
        )
        menu.addSeparator()

        has_frame = self.has_result()
        act_asc = menu.addAction(
            "Apply Ascending Order to Query",
            lambda: self.apply_query_order_requested.emit(h_name, "ASC"),
        )
        if act_asc is not None:
            act_asc.setEnabled(has_frame)
        act_desc = menu.addAction(
            "Apply Descending Order to Query",
            lambda: self.apply_query_order_requested.emit(h_name, "DESC"),
        )
        if act_desc is not None:
            act_desc.setEnabled(has_frame)
        menu.addSeparator()
        menu.addAction(
            "Copy Header Name",
            lambda: self._set_clipboard_text(h_name),
        )
        menu.addAction(
            "Copy Quoted Header",
            lambda: self._set_clipboard_text(format_header_name(h_name, quote=True)),
        )
        menu.addAction("Copy All Visible Column Names", self.copy_all_visible_column_names)
        menu.addSeparator()
        menu.addAction(
            "Insert Header into Editor",
            lambda: self.insert_header_requested.emit(h_name),
        )
        menu.addSeparator()
        menu.addAction("Hide Column", lambda: self.hide_column(column))
        menu.addAction("Show All Columns", self.show_all_columns)
        menu.addAction("Auto-size Columns", self.auto_size_columns)
        menu.addAction("Reset Columns to Default", self.reset_columns_default)
        return menu

    def create_body_context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction(
            "Copy",
            lambda: self.copy_selection(include_headers=False, quote_headers=False),
        )
        menu.addAction(
            "Copy with Column Names",
            lambda: self.copy_selection(include_headers=True, quote_headers=False),
        )
        menu.addAction(
            "Copy with Quoted Column Names",
            lambda: self.copy_selection(include_headers=True, quote_headers=True),
        )
        return menu

    def _on_header_context_menu_requested(self, pos: QPoint) -> None:
        header = self.horizontalHeader()
        if header is None:
            return
        column = header.logicalIndexAt(pos)
        if column >= 0:
            menu = self.create_header_context_menu(column)
            QMenu.exec(menu, header.mapToGlobal(pos))

    def _on_body_context_menu_requested(self, pos: QPoint) -> None:
        idx = self.indexAt(pos)
        viewport = self.viewport()
        if idx.isValid() and viewport is not None:
            menu = self.create_body_context_menu()
            QMenu.exec(menu, viewport.mapToGlobal(pos))

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e is not None and e.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
            e.accept()
        else:
            super().keyPressEvent(e)

    def copy_selection(self, include_headers: bool = False, quote_headers: bool = False) -> None:
        sel_model = self.selectionModel()
        header = self.horizontalHeader()
        if sel_model is None or header is None or self._proxy_model.rowCount() == 0:
            return

        selected_indexes = sel_model.selectedIndexes()
        if not selected_indexes:
            return

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
            self._set_clipboard_text(tsv_text)
