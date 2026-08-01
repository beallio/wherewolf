import polars as pl

from wherewolf.services.selection import selected_frame


def test_selected_frame_is_deterministic_and_visual() -> None:
    frame = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    assert selected_frame(frame, [(1, 0), (0, 0)], [2]).rows() == [(5,), (6,)]


def test_selected_frame_uses_moved_visible_columns_for_discontiguous_cells() -> None:
    frame = pl.DataFrame({"a": [1, 2], "hidden_b": [3, 4], "c": [5, 6]})

    exported = selected_frame(frame, [(1, 1), (0, 0), (1, 0)], [2, 0])

    assert exported.columns == ["c", "a"]
    assert exported.rows() == [(5, 1), (6, 2)]
