"""Pure-function serializers for formatting grid selections into clipboard text."""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

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

    sorted_cells = sorted(set(selected_list), key=lambda x: (x[0], x[1]))

    rows_dict: dict[int, list[int]] = {}
    for r, v_col in sorted_cells:
        if r not in rows_dict:
            rows_dict[r] = []
        rows_dict[r].append(v_col)

    used_visual_cols = sorted({v_col for _, v_col in sorted_cells})

    lines = []
    if include_headers:
        header_parts = []
        for v_col in used_visual_cols:
            m_col = column_order[v_col]
            h_name = frame.columns[m_col]
            header_parts.append(format_header_name(h_name, quote=quote_headers))
        lines.append("\t".join(header_parts))

    for r in sorted(rows_dict.keys()):
        v_cols = rows_dict[r]
        row_parts = []
        for v_col in v_cols:
            m_col = column_order[v_col]
            val = frame[r, m_col]
            row_parts.append(format_cell_value(val))
        lines.append("\t".join(row_parts))

    return "\n".join(lines)
