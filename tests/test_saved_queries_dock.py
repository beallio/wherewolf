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
