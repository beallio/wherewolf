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


def test_result_table_view_header_context_menu_actions(qtbot):
    df = pl.DataFrame({"col_a": [2, 10, 1], "col_b": ["x", "y", "z"]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(df)

    # Build header context menu for column 0
    menu = table_view.create_header_context_menu(0)
    actions = {action.text(): action for action in menu.actions()}

    assert "Sort Ascending" in actions
    assert "Sort Descending" in actions
    assert "Clear Sort" in actions
    assert "Copy Header Name" in actions
    assert "Copy Quoted Header" in actions
    assert "Insert Header into Editor" in actions

    # Sort Ascending action
    actions["Sort Ascending"].trigger()
    assert table_view.proxy_model().sortColumn() == 0
    assert table_view.proxy_model().sortOrder() == Qt.SortOrder.AscendingOrder

    # Sort Descending action
    actions["Sort Descending"].trigger()
    assert table_view.proxy_model().sortColumn() == 0
    assert table_view.proxy_model().sortOrder() == Qt.SortOrder.DescendingOrder

    # Clear Sort action
    actions["Clear Sort"].trigger()
    assert table_view.proxy_model().sortColumn() == -1

    # Copy Header Name action
    actions["Copy Header Name"].trigger()
    assert QApplication.clipboard().text() == "col_a"

    # Copy Quoted Header action
    actions["Copy Quoted Header"].trigger()
    assert QApplication.clipboard().text() == '"col_a"'

    # Insert Header into Editor signal
    inserted = []
    table_view.insert_header_requested.connect(inserted.append)
    actions["Insert Header into Editor"].trigger()
    assert inserted == ["col_a"]


def test_result_table_view_body_context_menu_actions(qtbot):
    df = pl.DataFrame({"a": [10, 20], "b": ["x", "y"]})
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

    menu = table_view.create_body_context_menu()
    actions = {action.text(): action for action in menu.actions()}

    assert "Copy" in actions
    assert "Copy with Column Names" in actions
    assert "Copy with Quoted Column Names" in actions

    actions["Copy"].trigger()
    assert QApplication.clipboard().text() == "10\tx\n20\ty"

    actions["Copy with Column Names"].trigger()
    assert QApplication.clipboard().text() == "a\tb\n10\tx\n20\ty"

    actions["Copy with Quoted Column Names"].trigger()
    assert QApplication.clipboard().text() == '"a"\t"b"\n10\tx\n20\ty'
