"""Tests for ResultTableView."""

from __future__ import annotations

from datetime import date

import polars as pl
from PyQt6.QtCore import QItemSelection, QItemSelectionModel, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.clipboard_serializers import serialize_to_tsv
from wherewolf.desktop.widgets.result_table_view import ResultTableView
from wherewolf.services.selection import selected_frame


def test_result_table_view_selection_and_copy(qtbot):
    df = pl.DataFrame({"a": [10, 20, 30], "b": ["x", "y", "z"]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)

    table_view.set_frame(df)

    # Select range (0, 0) to (1, 1)
    sel_model = table_view.selectionModel()
    assert sel_model is not None
    idx0 = table_view.proxy_model().index(0, 0)
    idx1 = table_view.proxy_model().index(1, 1)
    selection = QItemSelection(idx0, idx1)
    sel_model.select(
        selection,
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Clear,
    )

    # Trigger copy
    table_view.copy_selection()

    cb = QApplication.clipboard()
    assert cb is not None
    assert cb.text() == "10\tx\n20\ty"
    table_view.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_C,
            Qt.KeyboardModifier.ControlModifier,
        )
    )
    assert cb.text() == "10\tx\n20\ty"


def test_selection_for_export_maps_visual_columns_when_a_column_is_hidden(qtbot) -> None:
    frame = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(frame)
    table_view.hide_column(0)

    selection_model = table_view.selectionModel()
    assert selection_model is not None
    index = table_view.proxy_model().index(0, 1)
    selection_model.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    cells, column_order = table_view.selection_for_export()

    assert serialize_to_tsv(frame, cells, column_order) == "2"


def test_selection_export_frame_maps_visual_columns_when_a_column_is_hidden(qtbot) -> None:
    frame = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(frame)
    table_view.hide_column(0)

    selection_model = table_view.selectionModel()
    assert selection_model is not None
    index = table_view.proxy_model().index(0, 1)
    selection_model.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    cells, column_order = table_view.selection_for_export()

    assert selected_frame(frame, cells, column_order).to_dicts() == [{"b": 2}]


def test_selection_statistics_summarises_multiple_numeric_cells(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(pl.DataFrame({"number": [1, 2, 2]}))

    selection_model = table_view.selectionModel()
    assert selection_model is not None
    selection_model.select(
        QItemSelection(table_view.proxy_model().index(0, 0), table_view.proxy_model().index(2, 0)),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )

    statistics = table_view.selection_statistics()

    assert statistics is not None
    assert statistics.cell_count == 3
    assert statistics.distinct_count == 2
    assert statistics.null_count == 0
    assert statistics.numeric is not None
    assert statistics.numeric.total == 5
    assert statistics.numeric.mean == 5 / 3
    assert statistics.numeric.minimum == 1
    assert statistics.numeric.maximum == 2


def test_selection_statistics_marks_mixed_columns_non_numeric(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(pl.DataFrame({"number": [1, 2], "name": ["Ada", "Lin"]}))

    selection_model = table_view.selectionModel()
    assert selection_model is not None
    selection_model.select(
        QItemSelection(table_view.proxy_model().index(0, 0), table_view.proxy_model().index(1, 1)),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )

    statistics = table_view.selection_statistics()

    assert statistics is not None
    assert statistics.cell_count == 4
    assert statistics.distinct_count == 4
    assert statistics.null_count == 0
    assert statistics.numeric is None


def test_selection_statistics_counts_nulls_outside_numeric_aggregates(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(pl.DataFrame({"number": [1, None, 3]}))

    selection_model = table_view.selectionModel()
    assert selection_model is not None
    selection_model.select(
        QItemSelection(table_view.proxy_model().index(0, 0), table_view.proxy_model().index(2, 0)),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )

    statistics = table_view.selection_statistics()

    assert statistics is not None
    assert statistics.cell_count == 3
    assert statistics.distinct_count == 3
    assert statistics.null_count == 1
    assert statistics.numeric is not None
    assert statistics.numeric.total == 4
    assert statistics.numeric.mean == 2
    assert statistics.numeric.minimum == 1
    assert statistics.numeric.maximum == 3


def test_selection_statistics_returns_none_for_empty_and_single_cell_selections(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(pl.DataFrame({"number": [1, 2]}))

    assert table_view.selection_statistics() is None

    selection_model = table_view.selectionModel()
    assert selection_model is not None
    selection_model.select(
        table_view.proxy_model().index(0, 0), QItemSelectionModel.SelectionFlag.ClearAndSelect
    )

    assert table_view.selection_statistics() is None


def test_selection_statistics_maps_the_visible_column_when_a_column_is_hidden(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(pl.DataFrame({"hidden": [100, 200], "shown": [1, 2]}))
    table_view.hide_column(0)

    selection_model = table_view.selectionModel()
    assert selection_model is not None
    selection_model.select(
        QItemSelection(table_view.proxy_model().index(0, 1), table_view.proxy_model().index(1, 1)),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )

    statistics = table_view.selection_statistics()

    assert statistics is not None
    assert statistics.numeric is not None
    assert statistics.numeric.total == 3
    assert statistics.numeric.mean == 1.5
    assert statistics.numeric.minimum == 1
    assert statistics.numeric.maximum == 2


def test_result_table_view_uses_distinguishable_alternating_row_colors(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)

    assert table_view.alternatingRowColors()
    palette = table_view.palette()
    assert palette.alternateBase().color() != palette.base().color()


def test_result_table_view_copy_respects_sort(qtbot):
    df = pl.DataFrame({"num": [2, 10, 1]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)

    table_view.set_frame(df)
    # Sort ascending
    table_view.proxy_model().sort(0, Qt.SortOrder.AscendingOrder)

    # Select all rows in column 0
    sel_model = table_view.selectionModel()
    assert sel_model is not None
    idx0 = table_view.proxy_model().index(0, 0)
    idx2 = table_view.proxy_model().index(2, 0)
    selection = QItemSelection(idx0, idx2)
    sel_model.select(
        selection,
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Clear,
    )

    table_view.copy_selection()
    cb = QApplication.clipboard()
    assert cb is not None
    assert cb.text() == "1\n2\n10"


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
    assert "Copy All Visible Column Names" in actions
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

    cb = QApplication.clipboard()
    assert cb is not None

    # Copy Header Name action
    actions["Copy Header Name"].trigger()
    assert cb.text() == "col_a"

    # Copy Quoted Header action
    actions["Copy Quoted Header"].trigger()
    assert cb.text() == '"col_a"'

    # All-visible copy follows the current visual order and excludes hidden columns.
    table_view.move_column(1, 0)
    table_view.hide_column(0)
    actions["Copy All Visible Column Names"].trigger()
    assert cb.text() == "col_b"

    # Insert Header into Editor signal
    inserted: list[str] = []
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
    assert sel_model is not None
    idx0 = table_view.proxy_model().index(0, 0)
    idx1 = table_view.proxy_model().index(1, 1)
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

    cb = QApplication.clipboard()
    assert cb is not None

    actions["Copy"].trigger()
    assert cb.text() == "10\tx\n20\ty"

    actions["Copy with Column Names"].trigger()
    assert cb.text() == "a\tb\n10\tx\n20\ty"

    actions["Copy with Quoted Column Names"].trigger()
    assert cb.text() == '"a"\t"b"\n10\tx\n20\ty'


def test_result_table_view_column_operations(qtbot):
    df = pl.DataFrame({"col1": [1, 2], "col2": [10, 20], "col3": [100, 200]})
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(df)

    header = table_view.horizontalHeader()
    assert header is not None

    # Move visual column 0 to visual column 1
    table_view.move_column(0, 1)
    assert header.visualIndex(0) == 1
    assert header.visualIndex(1) == 0

    # Hide column 1
    table_view.hide_column(1)
    assert table_view.isColumnHidden(1) is True

    # Copy with hidden column: column 1 should be excluded from copy
    sel_model = table_view.selectionModel()
    assert sel_model is not None
    idx0 = table_view.proxy_model().index(0, 0)
    idx2 = table_view.proxy_model().index(0, 2)
    selection = QItemSelection(idx0, idx2)
    sel_model.select(
        selection,
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Clear,
    )
    table_view.copy_selection(include_headers=True)
    cb = QApplication.clipboard()
    assert cb is not None
    assert cb.text() == "col1\tcol3\n1\t100"

    # Reset columns default: restores order and visibility
    table_view.reset_columns_default()
    assert table_view.isColumnHidden(0) is False
    assert table_view.isColumnHidden(1) is False
    header = table_view.horizontalHeader()
    assert header is not None
    assert header.visualIndex(0) == 0
    assert header.visualIndex(1) == 1

    table_view.auto_size_columns()
    assert all(header.sectionSize(column) > 0 for column in range(3))


def test_result_table_view_auto_sizes_columns_with_a_configured_width_cap(qtbot) -> None:
    frame = pl.DataFrame({"wide": ["x" * 400], "narrow": ["ok"]})

    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_auto_size_policy(enabled=True, maximum_width=120)
    table_view.set_frame(frame)

    assert table_view.columnWidth(0) == 120
    assert table_view.columnWidth(1) < 120

    disabled_table_view = ResultTableView()
    qtbot.addWidget(disabled_table_view)
    disabled_table_view.set_auto_size_policy(enabled=False, maximum_width=120)
    disabled_table_view.set_frame(frame)

    assert disabled_table_view.columnWidth(0) != 120


def test_result_table_view_headers_show_distinct_dtype_badges_and_tooltips(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)
    table_view.set_frame(
        pl.DataFrame(
            {
                "count": [1],
                "name": ["Ada"],
                "started": [date(2026, 8, 2)],
                "active": [True],
            }
        )
    )

    header = table_view.horizontalHeader()
    assert header is not None
    model = table_view.model()
    assert model is not None

    badges = [
        model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.UserRole)
        for column in range(4)
    ]
    tooltips = [
        model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
        for column in range(4)
    ]

    assert badges == ["INT", "TXT", "DATE", "BOOL"]
    assert len(set(badges)) == 4
    display_headers = [
        model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        for column in range(4)
    ]
    assert display_headers == [
        "count [INT]",
        "name [TXT]",
        "started [DATE]",
        "active [BOOL]",
    ]
    assert "Int" in str(tooltips[0])
    assert "String" in str(tooltips[1])
    assert "Date" in str(tooltips[2])
    assert "Boolean" in str(tooltips[3])


def test_header_context_menu_apply_order(qtbot) -> None:
    table_view = ResultTableView()
    qtbot.addWidget(table_view)

    # 1. No result loaded: actions should be disabled
    menu = table_view.create_header_context_menu(0)
    asc_actions = [a for a in menu.actions() if "Apply Ascending" in a.text()]
    desc_actions = [a for a in menu.actions() if "Apply Descending" in a.text()]
    assert len(asc_actions) == 1
    assert len(desc_actions) == 1
    assert asc_actions[0].isEnabled() is False
    assert desc_actions[0].isEnabled() is False

    # 2. Result loaded: actions should be enabled and emit signal when triggered
    df = pl.DataFrame({"col_a": [1, 2]})
    table_view.set_frame(df)

    emitted: list[tuple[str, str]] = []
    table_view.apply_query_order_requested.connect(lambda col, dir: emitted.append((col, dir)))

    menu = table_view.create_header_context_menu(0)
    asc_actions = [a for a in menu.actions() if "Apply Ascending" in a.text()]
    desc_actions = [a for a in menu.actions() if "Apply Descending" in a.text()]
    assert asc_actions[0].isEnabled() is True
    assert desc_actions[0].isEnabled() is True

    asc_actions[0].trigger()
    assert len(emitted) == 1
    assert emitted[0] == ("col_a", "ASC")

    desc_actions[0].trigger()
    assert len(emitted) == 2
    assert emitted[1] == ("col_a", "DESC")


def test_local_sort_does_not_rerun_query(qtbot, monkeypatch) -> None:
    from wherewolf.desktop.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    executed_count = 0

    def mock_execute(request):
        nonlocal executed_count
        executed_count += 1
        return True

    monkeypatch.setattr(window.query_controller, "execute", mock_execute)

    # Populate grid
    df = pl.DataFrame({"a": [3, 1, 2], "b": ["z", "x", "y"]})
    window.result_table_view.set_frame(df)
    window.editor.setText("SELECT * FROM preview")

    assert executed_count == 0

    # Drive sorting through the view so a future header signal connection is exercised.
    window.result_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    window.result_table_view.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    window.result_table_view.sortByColumn(-1, Qt.SortOrder.AscendingOrder)

    # Local sort must NOT submit any new executions through QueryController
    assert executed_count == 0


def test_active_local_sort_discloses_that_only_the_preview_is_sorted(qtbot) -> None:
    from wherewolf.desktop.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.result_table_view.set_frame(pl.DataFrame({"a": [3, 1, 2]}))

    assert window.result_sort_notice.isHidden()

    window.result_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    assert not window.result_sort_notice.isHidden()
    assert window.result_sort_notice.text() == "Sorted preview only."

    window.result_table_view.sortByColumn(-1, Qt.SortOrder.AscendingOrder)

    assert window.result_sort_notice.isHidden()
