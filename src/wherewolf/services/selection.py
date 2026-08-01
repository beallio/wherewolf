"""Shared visual-grid selection rules for clipboard and preview exports."""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl


def ordered_selected_cells(
    selected_cells: Iterable[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    """Deduplicate cells and order a discontiguous selection by row then visual column."""
    return tuple(sorted(set(selected_cells), key=lambda cell: (cell[0], cell[1])))


def selected_rows(cells: Iterable[tuple[int, int]]) -> tuple[int, ...]:
    """Return the selected rows in deterministic visual-grid order."""
    return tuple(sorted({row for row, _ in cells}))


def selected_visual_columns(cells: Iterable[tuple[int, int]]) -> tuple[int, ...]:
    """Return visible selected columns in deterministic visual order."""
    return tuple(sorted({column for _, column in cells}))


def selected_frame(
    frame: pl.DataFrame, selected_cells: Iterable[tuple[int, int]], column_order: list[int]
) -> pl.DataFrame:
    """Return selected rows and visible columns in their deterministic visual order."""
    cells = ordered_selected_cells(selected_cells)
    if not cells:
        return pl.DataFrame()
    rows = selected_rows(cells)
    visual_columns = selected_visual_columns(cells)
    return frame.select([frame.columns[column_order[column]] for column in visual_columns]).gather(
        rows
    )
