import json
from typing import TypedDict

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QMessageBox

from wherewolf.storage.history import HistoryManager


class HistoryTestRecord(TypedDict):
    schema_version: int
    id: str
    timestamp: str
    engine: str
    query: str
    catalog: dict[str, object]


def _history_records() -> list[HistoryTestRecord]:
    return [
        {
            "schema_version": 2,
            "id": "9d313d6c-9d79-43c7-9877-36d127e99f62",
            "timestamp": "2026-08-03T12:00:00+00:00",
            "engine": "duckdb",
            "query": "SELECT first",
            "catalog": {},
        },
        {
            "schema_version": 2,
            "id": "4815baf4-75ea-4e0c-bfa6-87ab551a9898",
            "timestamp": "2026-08-03T12:01:00+00:00",
            "engine": "duckdb",
            "query": "SELECT second",
            "catalog": {},
        },
        {
            "schema_version": 2,
            "id": "b2305193-2d91-41e3-87a4-7da5f72d20ef",
            "timestamp": "2026-08-03T12:02:00+00:00",
            "engine": "duckdb",
            "query": "SELECT third",
            "catalog": {},
        },
    ]


def _item_with_id(dock, record_id: str):
    for row in range(dock.history_table.topLevelItemCount()):
        item = dock.history_table.topLevelItem(row)
        if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == record_id:
            return item
    raise AssertionError(f"History dock did not contain record {record_id}")


def _click_history_item(qtbot, dock, item, button, modifier=Qt.KeyboardModifier.NoModifier) -> None:
    rect = dock.history_table.visualItemRect(item)
    qtbot.mouseClick(dock.history_table.viewport(), button, modifier, rect.center())


def test_history_dock_deletes_multiple_selected_records_after_confirmation(
    tmp_path, qtbot, monkeypatch
):
    from wherewolf.desktop.widgets import history_dock
    from wherewolf.desktop.widgets.history_dock import HistoryDock

    records = _history_records()
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps(records))
    history_manager = HistoryManager(storage_path=history_file)
    dock = HistoryDock(history_manager)
    qtbot.addWidget(dock)

    first = _item_with_id(dock, records[0]["id"])
    second = _item_with_id(dock, records[1]["id"])
    dock.history_table.setCurrentItem(first)
    first.setSelected(True)
    second.setSelected(True)

    prompt_messages: list[str] = []

    def confirm_delete(*args):
        prompt_messages.append(args[2])
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(history_dock, "QMessageBox", QMessageBox, raising=False)
    monkeypatch.setattr(history_dock.QMessageBox, "question", confirm_delete)

    dock._delete_action.trigger()

    assert prompt_messages == ["Delete 2 history records? This cannot be undone."]
    assert [record["id"] for record in history_manager.get_all()] == [records[2]["id"]]
    assert dock.history_table.topLevelItemCount() == 1


def test_history_dock_cancelled_delete_keeps_selected_records(tmp_path, qtbot, monkeypatch):
    from wherewolf.desktop.widgets import history_dock
    from wherewolf.desktop.widgets.history_dock import HistoryDock

    records = _history_records()
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps(records))
    history_manager = HistoryManager(storage_path=history_file)
    dock = HistoryDock(history_manager)
    qtbot.addWidget(dock)

    first = _item_with_id(dock, records[0]["id"])
    second = _item_with_id(dock, records[1]["id"])
    dock.history_table.setCurrentItem(first)
    first.setSelected(True)
    second.setSelected(True)
    monkeypatch.setattr(history_dock, "QMessageBox", QMessageBox, raising=False)
    monkeypatch.setattr(
        history_dock.QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No
    )

    dock._delete_action.trigger()

    assert [record["id"] for record in history_manager.get_all()] == [
        record["id"] for record in records
    ]
    assert dock.history_table.topLevelItemCount() == 3


def test_history_dock_context_click_preserves_selected_rows_or_selects_clicked_row(tmp_path, qtbot):
    from wherewolf.desktop.widgets.history_dock import HistoryDock

    records = _history_records()
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps(records))
    dock = HistoryDock(HistoryManager(storage_path=history_file))
    qtbot.addWidget(dock)
    dock.show()

    assert dock.history_table.selectionMode() is QAbstractItemView.SelectionMode.ExtendedSelection

    first = _item_with_id(dock, records[0]["id"])
    second = _item_with_id(dock, records[1]["id"])
    third = _item_with_id(dock, records[2]["id"])
    _click_history_item(qtbot, dock, first, Qt.MouseButton.LeftButton)
    _click_history_item(
        qtbot,
        dock,
        second,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    selected_before_context_click = {
        item.data(0, Qt.ItemDataRole.UserRole) for item in dock.history_table.selectedItems()
    }
    assert selected_before_context_click == {records[0]["id"], records[1]["id"]}

    _click_history_item(qtbot, dock, first, Qt.MouseButton.RightButton)
    assert {
        item.data(0, Qt.ItemDataRole.UserRole) for item in dock.history_table.selectedItems()
    } == selected_before_context_click

    _click_history_item(qtbot, dock, third, Qt.MouseButton.RightButton)
    assert [
        item.data(0, Qt.ItemDataRole.UserRole) for item in dock.history_table.selectedItems()
    ] == [records[2]["id"]]


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


def test_history_first_column_can_be_reordered(tmp_path, qtbot):
    record = {
        "schema_version": 2,
        "id": "d1df60ca-c254-4601-b143-3643642a8e7e",
        "timestamp": "2026-08-02T12:34:56+00:00",
        "engine": "duckdb",
        "query": "SELECT 1",
        "catalog": {},
    }
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps([record]))

    from wherewolf.desktop.widgets.history_dock import HistoryDock

    dock = HistoryDock(HistoryManager(storage_path=history_file))
    qtbot.addWidget(dock)
    header = dock.history_table.header()
    assert header is not None
    assert header.isFirstSectionMovable()

    before = header.visualIndex(0)
    header.moveSection(0, 1)
    assert header.visualIndex(0) != before


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


def test_history_sorts_timestamps_chronologically_and_header_click_reverses_order(tmp_path, qtbot):
    records = [
        {
            "schema_version": 2,
            "id": "9bc2a83a-14f4-4b4a-905f-801cfd0473c1",
            "timestamp": "2026-08-02T10:00:00+00:00",
            "engine": "duckdb",
            "query": "SELECT oldest",
            "catalog": {},
        },
        {
            "schema_version": 2,
            "id": "8c07ca1f-8cc9-496d-bc75-e145df0f9606",
            # This is 30 minutes newer, despite sorting before the preceding string.
            "timestamp": "2026-08-02T09:30:00-01:00",
            "engine": "duckdb",
            "query": "SELECT newest",
            "catalog": {},
        },
    ]
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps(records))

    from wherewolf.desktop.widgets.history_dock import HistoryDock

    dock = HistoryDock(HistoryManager(storage_path=history_file))
    qtbot.addWidget(dock)
    dock.show()

    header = dock.history_table.header()
    assert header is not None
    newest = dock.history_table.topLevelItem(0)
    assert newest is not None
    assert dock.history_table.isSortingEnabled()
    assert header.sortIndicatorOrder() is Qt.SortOrder.DescendingOrder
    assert newest.data(0, Qt.ItemDataRole.UserRole) == "8c07ca1f-8cc9-496d-bc75-e145df0f9606"
    qtbot.mouseClick(
        header.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(header.sectionPosition(0) + 5, header.height() // 2),
    )

    assert header.sortIndicatorOrder() is Qt.SortOrder.AscendingOrder
    oldest = dock.history_table.topLevelItem(0)
    assert oldest is not None
    assert oldest.data(0, Qt.ItemDataRole.UserRole) == "9bc2a83a-14f4-4b4a-905f-801cfd0473c1"
