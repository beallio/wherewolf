"""Non-modal inspector for values that do not fit in the results grid."""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class CellInspectorWindow(QWidget):
    """Display a complete cell value without applying grid or TSV formatting."""

    MAX_DISPLAY_CHARACTERS = 100_000

    def __init__(self, value: object, column_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(f"Cell Inspector — {column_name}")
        self.resize(720, 480)

        self._full_text = self._format_value(value)
        display_text = self._full_text[: self.MAX_DISPLAY_CHARACTERS]
        is_truncated = len(display_text) < len(self._full_text)

        layout = QVBoxLayout(self)
        self.truncation_label = QLabel(
            (
                f"Display truncated at {self.MAX_DISPLAY_CHARACTERS:,} characters. "
                "Copy preserves the complete value."
            ),
            self,
        )
        self.truncation_label.setVisible(is_truncated)
        layout.addWidget(self.truncation_label)

        self.value_text = QPlainTextEdit(self)
        self.value_text.setReadOnly(True)
        self.value_text.setPlainText(display_text)
        self.value_text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout.addWidget(self.value_text)

        self.copy_button = QPushButton("Copy Full Value", self)
        self.copy_button.clicked.connect(self._copy_full_value)
        layout.addWidget(self.copy_button)

    @staticmethod
    def _format_value(value: object) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return value
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed, ensure_ascii=False, indent=2, default=str)
            return value
        return str(value)

    def _copy_full_value(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._full_text)
