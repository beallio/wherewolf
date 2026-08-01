"""Tests for TypedSortProxyModel."""

from __future__ import annotations

import datetime

import polars as pl
from PyQt6.QtCore import Qt

from wherewolf.desktop.models.polars_table_model import PolarsTableModel
from wherewolf.desktop.models.typed_sort_proxy_model import TypedSortProxyModel


def test_typed_sort_proxy_model_numeric_sorting():
    df = pl.DataFrame({"num": [2, 10, 1]})
    source = PolarsTableModel(df)
    proxy = TypedSortProxyModel()
    proxy.setSourceModel(source)

    # Sort ascending
    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    sorted_vals = [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(3)]
    assert sorted_vals == [1, 2, 10]

    # Sort descending
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    sorted_vals_desc = [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(3)]
    assert sorted_vals_desc == [10, 2, 1]


def test_typed_sort_proxy_model_date_and_string_sorting():
    df = pl.DataFrame(
        {
            "dt": [
                datetime.date(2026, 8, 1),
                datetime.date(2025, 1, 1),
                datetime.date(2026, 1, 1),
            ],
            "str": ["banana", "apple", "cherry"],
        }
    )
    source = PolarsTableModel(df)
    proxy = TypedSortProxyModel()
    proxy.setSourceModel(source)

    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    dates = [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(3)]
    assert dates == [
        datetime.date(2025, 1, 1),
        datetime.date(2026, 1, 1),
        datetime.date(2026, 8, 1),
    ]

    proxy.sort(1, Qt.SortOrder.AscendingOrder)
    strs = [proxy.data(proxy.index(r, 1), Qt.ItemDataRole.UserRole) for r in range(3)]
    assert strs == ["apple", "banana", "cherry"]


def test_typed_sort_proxy_model_null_ordering():
    # Rule: nulls last on ascending sort
    df = pl.DataFrame({"num": [2, None, 1, 10]})
    source = PolarsTableModel(df)
    proxy = TypedSortProxyModel()
    proxy.setSourceModel(source)

    # Ascending sort: nulls at the end
    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    vals_asc = [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(4)]
    assert vals_asc == [1, 2, 10, None]

    # Descending sort: nulls at the end
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    vals_desc = [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(4)]
    assert vals_desc == [10, 2, 1, None]


def test_typed_sort_proxy_model_third_click_reset():
    df = pl.DataFrame({"num": [2, 10, 1]})
    source = PolarsTableModel(df)
    proxy = TypedSortProxyModel()
    proxy.setSourceModel(source)

    proxy.toggle_sort(0)  # Ascending
    assert [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(3)] == [
        1,
        2,
        10,
    ]

    proxy.toggle_sort(0)  # Descending
    assert [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(3)] == [
        10,
        2,
        1,
    ]

    proxy.toggle_sort(0)  # Reset to original
    assert [proxy.data(proxy.index(r, 0), Qt.ItemDataRole.UserRole) for r in range(3)] == [
        2,
        10,
        1,
    ]


def test_typed_sort_proxy_model_search_and_filter():
    df = pl.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "name": ["Alice", "Bob", "Charlie", "David"],
            "city": ["New York", "London", "Paris", "New York"],
        }
    )
    source = PolarsTableModel(df)
    proxy = TypedSortProxyModel()
    proxy.setSourceModel(source)

    # Filter for "York"
    proxy.set_filter_text("York")
    assert proxy.rowCount() == 2

    # Assert exact values and source row mapping (not just count!)
    val_row0_id = proxy.data(proxy.index(0, 0), Qt.ItemDataRole.UserRole)
    val_row0_name = proxy.data(proxy.index(0, 1), Qt.ItemDataRole.UserRole)
    assert val_row0_id == 1
    assert val_row0_name == "Alice"

    val_row1_id = proxy.data(proxy.index(1, 0), Qt.ItemDataRole.UserRole)
    val_row1_name = proxy.data(proxy.index(1, 1), Qt.ItemDataRole.UserRole)
    assert val_row1_id == 4
    assert val_row1_name == "David"

    # Combine filter with active sort (sort by name descending)
    proxy.sort(1, Qt.SortOrder.DescendingOrder)
    assert proxy.data(proxy.index(0, 1), Qt.ItemDataRole.UserRole) == "David"
    assert proxy.data(proxy.index(1, 1), Qt.ItemDataRole.UserRole) == "Alice"

    # Clear filter restores all rows
    proxy.set_filter_text("")
    assert proxy.rowCount() == 4
