"""Tests for clipboard_serializers."""

from __future__ import annotations

import polars as pl

from wherewolf.desktop.clipboard_serializers import serialize_to_tsv


def test_serialize_contiguous_range():
    df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    cells = [(0, 0), (0, 1), (1, 0), (1, 1)]

    # Without headers
    tsv = serialize_to_tsv(df, cells)
    assert tsv == "1\tx\n2\ty"

    # With headers
    tsv_h = serialize_to_tsv(df, cells, include_headers=True)
    assert tsv_h == "a\tb\n1\tx\n2\ty"


def test_serialize_visual_column_order():
    df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    # Swap visual columns: visual 0 -> model 1 ("b"), visual 1 -> model 0 ("a")
    col_order = [1, 0]
    cells = [(0, 0), (0, 1), (1, 0), (1, 1)]

    tsv = serialize_to_tsv(df, cells, column_order=col_order, include_headers=True)
    assert tsv == "b\ta\nx\t1\ny\t2"


def test_serialize_quoted_headers():
    df = pl.DataFrame({"col_a": [10], "col_b": [20]})
    cells = [(0, 0), (0, 1)]

    tsv = serialize_to_tsv(df, cells, include_headers=True, quote_headers=True)
    assert tsv == '"col_a"\t"col_b"\n10\t20'


def test_serialize_discontiguous_selection():
    # Rule: discontiguous selection is sorted deterministically by (row, visual_col)
    df = pl.DataFrame({"a": [1, 2, 3], "b": [10, 20, 30]})
    # Select (2, 1), (0, 0), (0, 1) out of order
    cells = [(2, 1), (0, 0), (0, 1)]

    tsv = serialize_to_tsv(df, cells)
    assert tsv == "1\t10\n30"


def test_serialize_tabs_newlines_nulls():
    df = pl.DataFrame({"txt": ["hello\tworld", "line1\nline2", None]})
    cells = [(0, 0), (1, 0), (2, 0)]

    tsv = serialize_to_tsv(df, cells)
    assert tsv == '"hello\tworld"\n"line1\nline2"\n<null>'
