from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.widgets.value_counts_window import (
    ValueCount,
    ValueCountsChart,
    ValueCountsResult,
    ValueCountsWindow,
)
from wherewolf.domain import CatalogBinding
from wherewolf.domain.enums import EngineKind, SourceFormat


class _FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def value_counts(self, _entry, _column_name: str, limit: int):
        self.calls.append(limit)
        return (("a", 3), ("b", 1))[:limit], 2, 4

    def close(self) -> None:
        pass


class _FakeRegistry:
    def __init__(self, adapter: _FakeAdapter) -> None:
        self.adapter = adapter

    def create(self, kind: EngineKind, request_id):
        return self.adapter


def _binding() -> CatalogBinding:
    return CatalogBinding(uuid4(), "users", Path("users.csv"), SourceFormat.CSV)


def test_value_counts_chart_paints_zero_and_single_rows(qtbot) -> None:
    chart = ValueCountsChart()
    qtbot.addWidget(chart)
    for counts in ((), (ValueCount("a", 1, 100.0),)):
        chart.set_counts(counts)
        chart.resize(320, 180)
        assert chart.grab().size().width() == 320


def test_value_counts_window_reruns_when_limit_changes(qtbot) -> None:
    adapter = _FakeAdapter()
    window = ValueCountsWindow(_binding(), "category", _FakeRegistry(adapter))
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: adapter.calls == [50])

    window.limit_selector.setValue(1)
    qtbot.waitUntil(lambda: adapter.calls[-1:] == [1])

    assert window.table.rowCount() == 1


def test_value_counts_window_table_copies_tsv(qtbot) -> None:
    window = ValueCountsWindow(_binding(), "category", _FakeRegistry(_FakeAdapter()))
    qtbot.addWidget(window)
    window._on_result(
        ValueCountsResult(
            entry_id=window.entry.entry_id,
            column_name="category",
            counts=(ValueCount("a", 3, 75.0),),
            total_distinct=2,
        )
    )
    window.table.selectRow(0)
    window.table.setFocus()
    qtbot.keyClick(window.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

    clipboard = QApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "a\t3\t75.00%"
