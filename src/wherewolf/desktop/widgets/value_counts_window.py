"""Non-modal value-counts window and its palette-aware bar chart."""

from __future__ import annotations

from functools import partial

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wherewolf.desktop.clipboard_serializers import serialize_table_widget_to_tsv
from wherewolf.desktop.workers.value_counts_worker import (
    ValueCount,
    ValueCountsRegistry,
    ValueCountsResult,
    ValueCountsWorker,
)
from wherewolf.domain import CatalogBinding


class ValueCountsChart(QWidget):
    """Draw horizontal count bars using colours from the current widget palette."""

    ROW_HEIGHT = 24
    PADDING = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._counts: tuple[ValueCount, ...] = ()
        self.setMinimumHeight(120)

    def set_counts(self, counts: tuple[ValueCount, ...]) -> None:
        self._counts = tuple(counts)
        self.setMinimumHeight(len(self._counts) * self.ROW_HEIGHT + self.PADDING * 2)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.width(), len(self._counts) * self.ROW_HEIGHT + self.PADDING * 2)

    def paintEvent(
        self, a0: QPaintEvent | None
    ) -> None:  # pragma: no cover - QPainter is exercised by grab tests
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())
        if not self._counts:
            painter.end()
            return

        padding = self.PADDING
        label_width = max(80, min(220, self.width() // 3))
        bar_left = padding + label_width
        bar_width = max(1, self.width() - bar_left - padding)
        row_height = self.ROW_HEIGHT
        maximum = max((item.count for item in self._counts), default=0)
        metrics = painter.fontMetrics()
        text_colour = self.palette().text().color()
        bar_colour = self.palette().highlight().color()
        painter.setPen(text_colour)
        rect = a0.rect() if a0 is not None else self.rect()
        first = max(0, (rect.top() - padding) // row_height)
        last = min(len(self._counts) - 1, (rect.bottom() - padding) // row_height)
        for index in range(first, last + 1):
            item = self._counts[index]
            top = padding + index * row_height
            label = metrics.elidedText(
                "<null>" if item.value is None else str(item.value),
                Qt.TextElideMode.ElideRight,
                max(1, label_width - 4),
            )
            painter.drawText(
                padding, top, label_width - 4, row_height, Qt.AlignmentFlag.AlignVCenter, label
            )
            width = int(bar_width * item.count / maximum) if maximum else 0
            painter.fillRect(bar_left, top + 4, width, max(1, row_height - 8), bar_colour)
            painter.drawText(
                bar_left + 4,
                top,
                max(1, bar_width - 4),
                row_height,
                Qt.AlignmentFlag.AlignVCenter,
                str(item.count),
            )
        painter.end()


class _CopyTableWidget(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e is not None and e.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
            e.accept()
            return
        super().keyPressEvent(e)

    def copy_selection(self) -> None:
        app_clipboard = QApplication.clipboard()
        if app_clipboard is None:
            return
        text = serialize_table_widget_to_tsv(self)
        if text:
            app_clipboard.setText(text)

    def _show_context_menu(self, pos) -> None:
        if not self.indexAt(pos).isValid():
            return
        menu = QMenu(self)
        menu.addAction("Copy", self.copy_selection)
        viewport = self.viewport()
        if viewport is not None:
            QMenu.exec(menu, viewport.mapToGlobal(pos))


class ValueCountsWindow(QWidget):
    """Floating, non-modal Top N value-counts view for one schema column."""

    DEBOUNCE_MS = 300

    def __init__(
        self,
        entry: CatalogBinding,
        column_name: str,
        engine_registry: ValueCountsRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.entry = entry
        self.column_name = column_name
        self._engine_registry = engine_registry
        self._workers: list[ValueCountsWorker] = []
        self._current_worker: ValueCountsWorker | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(f"Value counts: {entry.alias}.{column_name}")

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Top N", self))
        self.limit_selector = QSpinBox(self)
        self.limit_selector.setObjectName("value_counts_limit")
        self.limit_selector.setRange(1, 10_000)
        self.limit_selector.setValue(50)
        self._limit_debounce = QTimer(self)
        self._limit_debounce.setSingleShot(True)
        self._limit_debounce.setInterval(self.DEBOUNCE_MS)
        self._limit_debounce.timeout.connect(self._run_worker)
        self.limit_selector.valueChanged.connect(lambda _value: self._limit_debounce.start())
        controls.addWidget(self.limit_selector)
        self.total_distinct_label = QLabel("Total distinct values: —", self)
        controls.addWidget(self.total_distinct_label)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.table = _CopyTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Value", "Count", "Percentage"])
        header = self.table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self.chart = ValueCountsChart(self)
        self.chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.chart_scroll_area = QScrollArea(self)
        self.chart_scroll_area.setWidgetResizable(True)
        self.chart_scroll_area.setWidget(self.chart)
        self.content_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.content_splitter.addWidget(self.table)
        self.content_splitter.addWidget(self.chart_scroll_area)
        layout.addWidget(self.content_splitter)
        self.status_label = QLabel("Loading…", self)
        layout.addWidget(self.status_label)
        self._run_worker()

    def _run_worker(self) -> None:
        worker = ValueCountsWorker(
            self._engine_registry,
            self.entry,
            self.column_name,
            self.limit_selector.value(),
            self,
        )
        worker.result_ready.connect(partial(self._on_result_from, worker))
        worker.finished.connect(
            lambda: self._workers.remove(worker) if worker in self._workers else None
        )
        self._workers.append(worker)
        worker.start()
        self._current_worker = worker

    def _on_result_from(self, worker: ValueCountsWorker, result: ValueCountsResult) -> None:
        if worker is not self._current_worker:
            return
        self._on_result(result)

    def _on_result(self, result: ValueCountsResult) -> None:
        if result.error_message is not None:
            self.status_label.setText(f"Value counts error: {result.error_message}")
            self.table.setRowCount(0)
            self.chart.set_counts(())
            return
        self.status_label.setText("")
        self.total_distinct_label.setText(f"Total distinct values: {result.total_distinct}")
        self.table.setRowCount(len(result.counts))
        for row, item in enumerate(result.counts):
            self.table.setItem(
                row, 0, QTableWidgetItem("<null>" if item.value is None else str(item.value))
            )
            self.table.setItem(row, 1, QTableWidgetItem(str(item.count)))
            self.table.setItem(row, 2, QTableWidgetItem(f"{item.percentage:.2f}%"))
        self.chart.set_counts(result.counts)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.quit()
                worker.wait(5000)
        self._workers.clear()
        super().closeEvent(a0)


__all__ = ["ValueCount", "ValueCountsChart", "ValueCountsResult", "ValueCountsWindow"]
