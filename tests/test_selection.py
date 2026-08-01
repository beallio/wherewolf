import polars as pl

from wherewolf.selection import selected_frame


def test_selected_frame_is_deterministic_and_visual() -> None:
    frame = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    assert selected_frame(frame, [(1, 0), (0, 0)], [2]).rows() == [(5,), (6,)]
