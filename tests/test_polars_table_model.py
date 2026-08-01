"""Tests for PolarsTableModel."""

from __future__ import annotations

import polars as pl
from PyQt6.QtCore import Qt

from wherewolf.desktop.models.polars_table_model import PolarsTableModel


def test_polars_table_model_basic():
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    model = PolarsTableModel(df)

    assert model.rowCount() == 3
    assert model.columnCount() == 2
    assert model.headerData(0, Qt.Orientation.Horizontal) == "a"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "b"
    assert model.headerData(0, Qt.Orientation.Vertical) == 1
    assert model.headerData(2, Qt.Orientation.Vertical) == 3

    idx0 = model.index(0, 0)
    assert model.data(idx0, Qt.ItemDataRole.DisplayRole) == "1"

    idx1 = model.index(1, 1)
    assert model.data(idx1, Qt.ItemDataRole.DisplayRole) == "y"


def test_polars_table_model_empty_frame():
    df = pl.DataFrame()
    model = PolarsTableModel(df)

    assert model.rowCount() == 0
    assert model.columnCount() == 0


def test_polars_table_model_empty_rows_with_columns():
    df = pl.DataFrame({"col1": [], "col2": []}, schema={"col1": pl.Int64, "col2": pl.Utf8})
    model = PolarsTableModel(df)

    assert model.rowCount() == 0
    assert model.columnCount() == 2
    assert model.headerData(0, Qt.Orientation.Horizontal) == "col1"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "col2"
