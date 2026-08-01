"""Widget for displaying translated SQL and translation diagnostics."""

from PyQt6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from wherewolf.services.translation_view_model import translate_sql_view


class TranslationPanel(QWidget):
    """Displays translated SQL for the current query statement and dialect pair."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._diag_label = QLabel(self)
        self._diag_label.setWordWrap(True)
        self._diag_label.hide()
        layout.addWidget(self._diag_label)

        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setReadOnly(True)
        layout.addWidget(self._text_edit)

    def update_translation(self, sql: str, source_dialect: str, target_dialect: str) -> None:
        """Update the panel with translation results for the given SQL and dialects."""
        res = translate_sql_view(sql, source_dialect, target_dialect)
        self._text_edit.setPlainText(res.translated_sql)

        if res.diagnostics:
            messages = [f"[{d.severity.upper()}] {d.message}" for d in res.diagnostics]
            self._diag_label.setText("\n".join(messages))
            self._diag_label.show()
        else:
            self._diag_label.setText("")
            self._diag_label.hide()

    def translated_text(self) -> str:
        """Return the translated SQL text displayed in the panel."""
        return self._text_edit.toPlainText()

    def has_diagnostics(self) -> bool:
        """Return True if any translation diagnostics are present."""
        return not self._diag_label.isHidden() and bool(self._diag_label.text())

    def diagnostics_text(self) -> str:
        """Return the text of any displayed diagnostics."""
        return self._diag_label.text()
