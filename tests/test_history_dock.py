import json

from PyQt6.QtWidgets import QHeaderView

from wherewolf.storage.history import HistoryManager


def test_history_dock_selects_duplicate_labels_by_stable_id(tmp_path, qtbot):
    from wherewolf.desktop.widgets.history_dock import HistoryDock

    query_prefix = "SELECT " + "x" * 100
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

    assert dock.history_table.topLevelItemCount() == 2
    first_item = dock.history_table.topLevelItem(0)
    second_item = dock.history_table.topLevelItem(1)
    assert first_item is not None
    assert second_item is not None
    assert first_item.text(0) == second_item.text(0)
    assert first_item.text(1) == second_item.text(1)
    assert first_item.toolTip(1) == records[0]["query"]
    assert dock.history_table.alternatingRowColors()

    # The visible list is deliberately stale after a new record arrives. A row-index lookup
    # would now resolve the first original record, while UUID lookup still resolves this item.
    dock._history_manager.add_entry("duckdb", "SELECT intervening_record")
    with qtbot.waitSignal(dock.record_selected) as selected:
        dock.history_table.itemActivated.emit(second_item, 1)

    assert selected.args == [records[1]]


def test_history_timestamp_column_is_resizable(tmp_path, qtbot):
    record = {
        "schema_version": 2,
        "id": "d1df60ca-c254-4601-b143-3643642a8e7e",
        "timestamp": "2026-08-02T12:34:56.789123+00:00",
        "engine": "duckdb",
        "query": "SELECT 1",
        "catalog": {},
    }
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps([record]))

    from wherewolf.desktop.widgets.history_dock import HistoryDock

    dock = HistoryDock(HistoryManager(storage_path=history_file))
    qtbot.addWidget(dock)
    item = dock.history_table.topLevelItem(0)
    assert item is not None
    header = dock.history_table.header()
    assert header is not None

    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Interactive
    before = header.sectionSize(0)
    header.resizeSection(0, before + 75)
    assert header.sectionSize(0) == before + 75


def test_history_timestamp_hides_microseconds_and_keeps_raw_value_in_tooltip(tmp_path, qtbot):
    record = {
        "schema_version": 2,
        "id": "d1df60ca-c254-4601-b143-3643642a8e7e",
        "timestamp": "2026-08-02T12:34:56.789123+00:00",
        "engine": "duckdb",
        "query": "SELECT 1",
        "catalog": {},
    }
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps([record]))

    from wherewolf.desktop.widgets.history_dock import HistoryDock

    dock = HistoryDock(HistoryManager(storage_path=history_file))
    qtbot.addWidget(dock)
    item = dock.history_table.topLevelItem(0)
    assert item is not None

    assert item.text(0) == "2026-08-02T12:34:56+00:00"
    assert item.toolTip(0) == record["timestamp"]
