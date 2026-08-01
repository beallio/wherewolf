"""Tests for PolarsTableModel."""

from __future__ import annotations

import datetime

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


def test_polars_table_model_roles_and_nulls():
    df = pl.DataFrame(
        {
            "num": [42, None],
            "dt": [datetime.date(2026, 8, 1), None],
            "txt": ["null", None],
        }
    )
    model = PolarsTableModel(df)

    # UserRole returns typed Python values
    val_num_0 = model.data(model.index(0, 0), Qt.ItemDataRole.UserRole)
    assert val_num_0 == 42
    assert isinstance(val_num_0, int)

    val_dt_0 = model.data(model.index(0, 1), Qt.ItemDataRole.UserRole)
    assert val_dt_0 == datetime.date(2026, 8, 1)

    val_txt_0 = model.data(model.index(0, 2), Qt.ItemDataRole.UserRole)
    assert val_txt_0 == "null"

    val_null = model.data(model.index(1, 0), Qt.ItemDataRole.UserRole)
    assert val_null is None

    # DisplayRole returns string representations
    disp_txt_0 = model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole)
    disp_txt_null = model.data(model.index(1, 2), Qt.ItemDataRole.DisplayRole)

    assert disp_txt_0 == "null"
    assert disp_txt_null == "<null>"
    assert disp_txt_null != "None"
    assert disp_txt_null != disp_txt_0
