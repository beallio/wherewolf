"""Pure-function serializers for formatting grid selections into clipboard text."""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl
from PyQt6.QtWidgets import QTableWidget

from wherewolf.services.selection import (
    ordered_selected_cells,
    selected_rows,
    selected_visual_columns,
)

NULL_PLACEHOLDER = "<null>"


def format_cell_value(val: object) -> str:
    if val is None:
        return NULL_PLACEHOLDER
    s = str(val)
    if any(c in s for c in ("\t", "\n", "\r", '"')):
        s = '"' + s.replace('"', '""') + '"'
    return s


def format_header_name(name: str, quote: bool = False) -> str:
    if quote:
        return '"' + name.replace('"', '""') + '"'
    if any(c in name for c in ("\t", "\n", "\r")):
        return '"' + name.replace('"', '""') + '"'
    return name


def serialize_to_tsv(
    frame: pl.DataFrame,
    selected_cells: Iterable[tuple[int, int]],
    column_order: list[int] | None = None,
    include_headers: bool = False,
    quote_headers: bool = False,
) -> str:
    """Serialize selected (row, col) cells from frame into TSV string.

    - selected_cells contains (row, visual_col) pairs.
    - column_order maps visual_col -> model_col.
    - Discontiguous selection rule: sorted deterministically by (row, visual_col).
    - Rows are separated by '\\n', cells within a row by '\\t'.
    """
    selected_list = list(selected_cells)
    if not selected_list or frame.is_empty():
        return ""

    if column_order is None:
        column_order = list(range(frame.width))

    sorted_cells = ordered_selected_cells(selected_list)
    rows = selected_rows(sorted_cells)
    used_visual_cols = selected_visual_columns(sorted_cells)

    lines = []
    if include_headers:
        header_parts = []
        for v_col in used_visual_cols:
            m_col = column_order[v_col]
            h_name = frame.columns[m_col]
            header_parts.append(format_header_name(h_name, quote=quote_headers))
        lines.append("\t".join(header_parts))

    for r in rows:
        v_cols = tuple(v_col for cell_row, v_col in sorted_cells if cell_row == r)
        row_parts = []
        for v_col in v_cols:
            m_col = column_order[v_col]
            val = frame[r, m_col]
            row_parts.append(format_cell_value(val))
        lines.append("\t".join(row_parts))

    return "\n".join(lines)


def serialize_table_widget_to_tsv(table: QTableWidget) -> str:
    """Serialize the selected cells of a read-only Qt table using the TSV rules above."""
    selection_model = table.selectionModel()
    if selection_model is None:
        return ""
    selected = {(index.row(), index.column()) for index in selection_model.selectedIndexes()}
    if not selected:
        return ""
    rows = sorted({row for row, _ in selected})
    row_positions = {row: position for position, row in enumerate(rows)}
    column_count = table.columnCount()
    headers = [table.horizontalHeaderItem(column) for column in range(column_count)]
    columns = [header.text() if header is not None else "" for header in headers]
    values: list[list[str]] = []
    for row in rows:
        row_values: list[str] = []
        for column in range(column_count):
            item = table.item(row, column)
            row_values.append(item.text() if item is not None else "")
        values.append(row_values)
    frame = pl.DataFrame(values, schema=columns, orient="row")
    selected_cells = [(row_positions[row], column) for row, column in selected]
    return serialize_to_tsv(frame, selected_cells)
