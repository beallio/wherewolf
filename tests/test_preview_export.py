from pathlib import Path

import polars as pl
import pytest

from wherewolf.services.export_destination import ExportFormat
from wherewolf.services.preview_export import write_preview, write_selection


@pytest.mark.parametrize("fmt", list(ExportFormat))
def test_preview_exports_reopen_with_columns_and_row_order(
    tmp_path: Path, fmt: ExportFormat
) -> None:
    source = pl.DataFrame({"a": [2, 1], "b": ["two", "one"]})
    path = tmp_path / f"result.{fmt.value}"
    write_preview(source, path, fmt)
    reopened = (
        pl.read_excel(path)
        if fmt is ExportFormat.XLSX
        else (pl.read_csv(path) if fmt is ExportFormat.CSV else pl.read_parquet(path))
    )
    assert reopened.rows() == source.rows()
    assert reopened.columns == source.columns


def test_selection_export_reuses_visual_column_order(tmp_path: Path) -> None:
    source = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    path = tmp_path / "selection.csv"
    write_selection(source, [(1, 0), (0, 0), (1, 1)], [2, 0], path, ExportFormat.CSV)
    assert pl.read_csv(path).columns == ["c", "a"]
    assert pl.read_csv(path).rows() == [(5, 1), (6, 2)]
