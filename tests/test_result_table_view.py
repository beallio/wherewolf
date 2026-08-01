"""Tests for ResultTableView."""

from __future__ import annotations

import polars as pl
from PyQt6.QtCore import QItemSelection, QItemSelectionModel, Qt
from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.widgets.result_table_view import ResultTableView


def test_result_table_view_selection_and_copy(qtbot):
    df = pl.DataFrame({"a": [10, 20, 30], "b": ["x", "y", "z"]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)

    table_view.set_frame(df)

    # Select range (0, 0) to (1, 1)
    sel_model = table_view.selectionModel()
    idx0 = table_view.model().index(0, 0)
    idx1 = table_view.model().index(1, 1)
    selection = QItemSelection(idx0, idx1)
    sel_model.select(
        selection,
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Clear,
    )

    # Trigger copy
    table_view.copy_selection()

    clipboard_text = QApplication.clipboard().text()
    assert clipboard_text == "10\tx\n20\ty"


def test_result_table_view_copy_respects_sort(qtbot):
    df = pl.DataFrame({"num": [2, 10, 1]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)

    table_view.set_frame(df)
    # Sort ascending
    table_view.proxy_model().sort(0, Qt.SortOrder.AscendingOrder)

    # Select all rows in column 0
    sel_model = table_view.selectionModel()
    idx0 = table_view.model().index(0, 0)
    idx2 = table_view.model().index(2, 0)
    selection = QItemSelection(idx0, idx2)
    sel_model.select(
        selection,
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Clear,
    )

    table_view.copy_selection()
    assert QApplication.clipboard().text() == "1\n2\n10"
