"""Bounded preview and selection exporters."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl

from wherewolf.services.export_destination import ExportFormat, write_atomically
from wherewolf.services.selection import selected_frame


def write_preview(frame: pl.DataFrame, destination: Path, export_format: ExportFormat) -> None:
    def write(path: Path) -> None:
        if export_format is ExportFormat.CSV:
            frame.write_csv(path)
        elif export_format is ExportFormat.XLSX:
            frame.write_excel(path)
        else:
            frame.write_parquet(path)

    write_atomically(destination, write)


def write_selection(
    frame: pl.DataFrame,
    selected_cells: Iterable[tuple[int, int]],
    column_order: list[int],
    destination: Path,
    export_format: ExportFormat,
) -> None:
    write_preview(selected_frame(frame, selected_cells, column_order), destination, export_format)
