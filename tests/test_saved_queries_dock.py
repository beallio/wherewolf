from __future__ import annotations

from PyQt6.QtCore import Qt

from wherewolf.storage import SavedQueryStore


def _visible_query_names(dock) -> list[str]:
    return [
        dock.query_list.item(index).text()
        for index in range(dock.query_list.count())
        if not dock.query_list.item(index).isHidden()
    ]


def test_saved_queries_dock_filters_and_emits_context_actions(tmp_path, qtbot) -> None:
    from wherewolf.desktop.widgets.saved_queries_dock import SavedQueriesDock

    store = SavedQueryStore(tmp_path / "saved_queries.json")
    daily = store.save_query(name="Daily quality check", description="", sql="SELECT 1")
    store.save_query(name="Monthly summary", description="", sql="SELECT 2")
    dock = SavedQueriesDock(store)
    qtbot.addWidget(dock)

    dock.query_filter.setText("daily")

    assert _visible_query_names(dock) == ["Daily quality check"]

    item = dock.query_list.item(0)
    assert item is not None
    dock.query_list.setCurrentItem(item)
    with qtbot.waitSignal(dock.run_requested) as emitted:
        dock._run_action.trigger()

    assert emitted.args == [daily]
    assert item.data(Qt.ItemDataRole.UserRole) == daily.id


def test_saved_queries_dock_filters_and_emits_from_one_refresh_snapshot(
    tmp_path, qtbot, monkeypatch
) -> None:
    from wherewolf.desktop.widgets.saved_queries_dock import SavedQueriesDock

    store = SavedQueryStore(tmp_path / "saved_queries.json")
    queries = [
        store.save_query(name=f"Query {index}", description="stable", sql=f"SELECT {index}")
        for index in range(20)
    ]
    calls = {"get_all": 0, "get_by_id": 0}
    original_get_all = store.get_all
    original_get_by_id = store.get_by_id
    monkeypatch.setattr(
        store,
        "get_all",
        lambda: calls.__setitem__("get_all", calls["get_all"] + 1) or original_get_all(),
    )
    monkeypatch.setattr(
        store,
        "get_by_id",
        lambda query_id: (
            calls.__setitem__("get_by_id", calls["get_by_id"] + 1) or original_get_by_id(query_id)
        ),
    )
    dock = SavedQueriesDock(store)
    qtbot.addWidget(dock)

    dock.query_filter.setText("query")
    dock.query_filter.setText("query 1")
    item = dock.query_list.item(1)
    assert item is not None
    dock.query_list.setCurrentItem(item)
    with qtbot.waitSignal(dock.run_requested) as emitted:
        dock._run_action.trigger()

    assert calls == {"get_all": 1, "get_by_id": 0}
    assert emitted.args == [queries[1]]
