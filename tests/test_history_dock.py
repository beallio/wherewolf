import json

from wherewolf.storage.history import HistoryManager


def test_history_dock_selects_duplicate_labels_by_stable_id(tmp_path, qtbot):
    from wherewolf.desktop.widgets.history_dock import HistoryDock

    query_prefix = "SELECT " + "x" * 30
    records = [
        {
            "schema_version": 2,
            "id": "5bb31a12-165e-4a7d-b4f6-439d78c0d50d",
            "timestamp": "2026-08-01T12:00:00+00:00",
            "engine": "duckdb",
            "query": f"{query_prefix} first",
            "catalog": {},
        },
        {
            "schema_version": 2,
            "id": "b1c6bb5a-4152-4617-8ec7-dc165d53d5d3",
            "timestamp": "2026-08-01T12:00:00+00:00",
            "engine": "duckdb",
            "query": f"{query_prefix} second",
            "catalog": {},
        },
    ]
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps(records))
    dock = HistoryDock(HistoryManager(storage_path=history_file))
    qtbot.addWidget(dock)

    assert dock.history_list.count() == 2
    first_item = dock.history_list.item(0)
    second_item = dock.history_list.item(1)
    assert first_item is not None
    assert second_item is not None
    assert first_item.text() == second_item.text()

    with qtbot.waitSignal(dock.record_selected) as selected:
        dock.history_list.itemActivated.emit(second_item)

    assert selected.args == [records[1]]
