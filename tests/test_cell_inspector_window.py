"""Tests for the non-modal result-cell inspector."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.widgets.cell_inspector_window import CellInspectorWindow


def test_cell_inspector_window_renders_long_strings_in_full(qtbot) -> None:
    value = "Wherewolf " * 100
    window = CellInspectorWindow(value, "note")
    qtbot.addWidget(window)

    assert window.value_text.toPlainText() == value


def test_cell_inspector_window_pretty_prints_structured_values(qtbot) -> None:
    window = CellInspectorWindow({"user": {"name": "Ada"}, "scores": [1, 2]}, "payload")
    qtbot.addWidget(window)

    assert window.value_text.toPlainText() == (
        '{\n  "user": {\n    "name": "Ada"\n  },\n  "scores": [\n    1,\n    2\n  ]\n}'
    )


def test_cell_inspector_window_keeps_invalid_json_like_strings_verbatim(qtbot) -> None:
    value = "{this is not valid JSON}"
    window = CellInspectorWindow(value, "payload")
    qtbot.addWidget(window)

    assert window.value_text.toPlainText() == value


def test_cell_inspector_window_marks_display_truncation(qtbot) -> None:
    value = "x" * (CellInspectorWindow.MAX_DISPLAY_CHARACTERS + 1)
    window = CellInspectorWindow(value, "payload")
    qtbot.addWidget(window)

    assert len(window.value_text.toPlainText()) < len(value)
    assert not window.truncation_label.isHidden()
    assert "truncated" in window.truncation_label.text().lower()


def test_cell_inspector_window_copies_the_untruncated_value(qtbot) -> None:
    value = "x" * (CellInspectorWindow.MAX_DISPLAY_CHARACTERS + 1)
    window = CellInspectorWindow(value, "payload")
    qtbot.addWidget(window)

    window.copy_button.click()

    clipboard = QApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == value
