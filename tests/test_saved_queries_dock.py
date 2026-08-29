from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt

from wherewolf.storage import SavedQueryDirectory


def _visible_query_names(dock) -> list[str]:
    return [
        dock.query_list.item(index).text()
        for index in range(dock.query_list.count())
        if not dock.query_list.item(index).isHidden()
    ]


def test_saved_queries_dock_filters_and_emits_context_actions(tmp_path, qtbot) -> None:
    from wherewolf.desktop.widgets.saved_queries_dock import SavedQueriesDock

    library = SavedQueryDirectory(tmp_path / "queries")
    daily = library.save_query(name="Daily quality check", sql="SELECT 1")
    library.save_query(name="reports/Monthly summary", sql="SELECT 2")
    dock = SavedQueriesDock(library)
    qtbot.addWidget(dock)

    assert _visible_query_names(dock) == ["Daily quality check", "reports/Monthly summary"]

    dock.query_filter.setText("daily")

    assert _visible_query_names(dock) == ["Daily quality check"]

    item = dock.query_list.item(0)
    assert item is not None
    dock.query_list.setCurrentItem(item)
    with qtbot.waitSignal(dock.run_requested) as emitted:
        dock._run_action.trigger()

    assert emitted.args == [daily]
    assert (
        item.data(Qt.ItemDataRole.UserRole)
        == daily.id
        == str(tmp_path / "queries" / "Daily quality check.sql")
    )


def test_saved_queries_dock_filters_and_emits_from_one_refresh_snapshot(
    tmp_path, qtbot, monkeypatch
) -> None:
    from wherewolf.desktop.widgets.saved_queries_dock import SavedQueriesDock

    library = SavedQueryDirectory(tmp_path / "queries")
    queries = [
        library.save_query(name=f"Query {index}", sql=f"-- stable\nSELECT {index}")
        for index in range(20)
    ]
    calls = {"get_all": 0}
    original_get_all = library.get_all
    monkeypatch.setattr(
        library,
        "get_all",
        lambda: calls.__setitem__("get_all", calls["get_all"] + 1) or original_get_all(),
    )
    dock = SavedQueriesDock(library)
    qtbot.addWidget(dock)

    dock.query_filter.setText("query")
    dock.query_filter.setText("query 1")
    item = dock.query_list.item(1)
    assert item is not None
    dock.query_list.setCurrentItem(item)
    with qtbot.waitSignal(dock.run_requested) as emitted:
        dock._run_action.trigger()

    assert calls == {"get_all": 1}
    assert emitted.args == [queries[1]]


def test_saved_queries_dock_filter_matches_the_leading_comment(tmp_path, qtbot) -> None:
    from wherewolf.desktop.widgets.saved_queries_dock import SavedQueriesDock

    library = SavedQueryDirectory(tmp_path / "queries")
    library.save_query(name="opaque", sql="-- Counts the weekly export.\nSELECT 1")
    library.save_query(name="other", sql="SELECT 2")
    dock = SavedQueriesDock(library)
    qtbot.addWidget(dock)

    dock.query_filter.setText("weekly export")

    assert _visible_query_names(dock) == ["opaque"]
    tooltip_item = dock.query_list.item(0)
    assert tooltip_item is not None
    assert tooltip_item.toolTip() == "Counts the weekly export."


def test_saved_queries_dock_refresh_action_requests_a_rescan(tmp_path, qtbot) -> None:
    from wherewolf.desktop.widgets.saved_queries_dock import SavedQueriesDock

    library = SavedQueryDirectory(tmp_path / "queries")
    library.save_query(name="first", sql="SELECT 1")
    dock = SavedQueriesDock(library)
    qtbot.addWidget(dock)

    library.save_query(name="second", sql="SELECT 2")

    assert _visible_query_names(dock) == ["first"]

    with qtbot.waitSignal(dock.refresh_requested):
        dock._refresh_action.trigger()

    dock.refresh()

    assert _visible_query_names(dock) == ["first", "second"]


def test_saved_queries_dock_shows_nothing_for_a_missing_directory(tmp_path, qtbot) -> None:
    from wherewolf.desktop.widgets.saved_queries_dock import SavedQueriesDock

    dock = SavedQueriesDock(SavedQueryDirectory(Path(tmp_path / "absent")))
    qtbot.addWidget(dock)

    assert dock.query_list.count() == 0
