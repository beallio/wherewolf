"""Shared visual-grid selection logic, independent of Qt and export formats."""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl


def selected_frame(
    frame: pl.DataFrame, selected_cells: Iterable[tuple[int, int]], column_order: list[int]
) -> pl.DataFrame:
    """Return selected rows/visible columns in their deterministic visual order."""
    cells = sorted(set(selected_cells), key=lambda cell: (cell[0], cell[1]))
    if not cells:
        return pl.DataFrame()
    rows = sorted({row for row, _ in cells})
    visual_columns = sorted({column for _, column in cells})
    return frame.select([frame.columns[column_order[column]] for column in visual_columns]).gather(
        rows
    )
