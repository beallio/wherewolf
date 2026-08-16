from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.widgets.value_counts_window import (
    ValueCount,
    ValueCountsChart,
    ValueCountsResult,
    ValueCountsWindow,
)
from wherewolf.desktop.workers.value_counts_worker import ValueCountsWorker
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


def test_value_counts_chart_has_a_scrollable_height_for_full_results(qtbot) -> None:
    adapter = _FakeAdapter()
    window = ValueCountsWindow(_binding(), "category", _FakeRegistry(adapter))
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.table.rowCount() == 2)
    window.resize(800, 700)
    window.show()
    counts = tuple(ValueCount(f"v{index}", 100 - index, 1.0) for index in range(50))
    window._on_result(
        ValueCountsResult(
            entry_id=window.entry.entry_id,
            column_name="category",
            counts=counts,
            total_distinct=50,
        )
    )

    qtbot.waitUntil(lambda: window.chart.minimumHeight() >= 50 * window.chart.ROW_HEIGHT)
    viewport = window.chart_scroll_area.viewport()
    assert viewport is not None
    viewport_height = viewport.height()
    scrollbar = window.chart_scroll_area.verticalScrollBar()
    assert scrollbar is not None
    qtbot.waitUntil(lambda: scrollbar.maximum() > 0)

    assert window.chart.minimumHeight() > viewport_height
    assert scrollbar.maximum() > 0

    window._on_result(
        ValueCountsResult(
            entry_id=window.entry.entry_id,
            column_name="category",
            counts=counts[:2],
            total_distinct=2,
        )
    )
    qtbot.waitUntil(lambda: scrollbar.maximum() == 0)


def test_value_counts_chart_culls_large_result_paints(qtbot) -> None:
    chart = ValueCountsChart()
    qtbot.addWidget(chart)
    counts = tuple(ValueCount(f"v{index}", 10_000 - index, 1.0) for index in range(10_000))
    chart.set_counts(counts)
    chart.resize(600, 400)

    assert chart.sizeHint().height() == len(counts) * chart.ROW_HEIGHT + chart.PADDING * 2
    assert chart.grab(QRect(0, 0, 600, 400)).size().height() == 400


def test_value_counts_chart_paints_rows_at_fixed_height(qtbot) -> None:
    chart = ValueCountsChart()
    qtbot.addWidget(chart)
    chart.set_counts(
        (
            ValueCount("first", 3, 50.0),
            ValueCount("second", 2, 33.0),
            ValueCount("third", 1, 17.0),
        )
    )
    chart.resize(600, 200)

    image = chart.grab().toImage()
    label_width = max(80, min(220, chart.width() // 3))
    bar_left = chart.PADDING + label_width
    third_bar_top = chart.PADDING + 2 * chart.ROW_HEIGHT + 4

    assert image.pixelColor(bar_left, third_bar_top) == chart.palette().highlight().color()


def test_value_counts_window_reruns_when_limit_changes(qtbot) -> None:
    adapter = _FakeAdapter()
    window = ValueCountsWindow(_binding(), "category", _FakeRegistry(adapter))
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: adapter.calls == [50])

    window.limit_selector.setValue(1)
    qtbot.waitUntil(lambda: adapter.calls[-1:] == [1])

    assert window.table.rowCount() == 1


def test_value_counts_window_debounces_rapid_limit_changes(qtbot) -> None:
    adapter = _FakeAdapter()
    window = ValueCountsWindow(_binding(), "category", _FakeRegistry(adapter))
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: adapter.calls == [50])

    window.limit_selector.setValue(10)
    window.limit_selector.setValue(20)
    window.limit_selector.setValue(30)

    qtbot.waitUntil(
        lambda: len(adapter.calls) >= 2,
        timeout=ValueCountsWindow.DEBOUNCE_MS + 1_000,
    )

    assert adapter.calls == [50, 30]


def test_value_counts_window_ignores_stale_worker_results(qtbot) -> None:
    adapter = _FakeAdapter()
    window = ValueCountsWindow(_binding(), "category", _FakeRegistry(adapter))
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.table.rowCount() == 2)
    current_worker = ValueCountsWorker(_FakeRegistry(adapter), window.entry, "category", 30, window)
    stale_worker = ValueCountsWorker(_FakeRegistry(adapter), window.entry, "category", 10, window)
    window._current_worker = current_worker

    window._on_result_from(
        stale_worker,
        ValueCountsResult(
            entry_id=window.entry.entry_id,
            column_name="category",
            counts=(ValueCount("stale", 1, 100.0),),
            total_distinct=1,
        ),
    )

    assert window.table.rowCount() == 2


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
