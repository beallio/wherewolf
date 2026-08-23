"""Widget for displaying execution errors, diagnostics, and system messages with severity roles."""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wherewolf.desktop.theming import message_severity_color
from wherewolf.domain.enums import ExecutionStatus
from wherewolf.domain.models import QueryResult, SqlDiagnostic


class MessagesPanel(QWidget):
    """Panel displaying application messages, SQL diagnostics, and execution errors with severity."""

    diagnostic_activated = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._list_widget = QListWidget(self)
        self._list_widget.setObjectName("messages_list")
        self._recently_activated_item: QListWidgetItem | None = None
        self._list_widget.itemActivated.connect(self._on_item_activated)
        self._list_widget.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self._list_widget)
        self.error_details_toggle = QToolButton(self)
        self.error_details_toggle.setObjectName("error_details_toggle")
        self.error_details_toggle.setText("Show raw error details")
        self.error_details_toggle.setCheckable(True)
        self.error_details_toggle.setVisible(False)
        self.error_details = QPlainTextEdit(self)
        self.error_details.setObjectName("error_details")
        self.error_details.setReadOnly(True)
        self.error_details.setVisible(False)
        self.error_details_toggle.toggled.connect(self.error_details.setVisible)
        layout.addWidget(self.error_details_toggle)
        layout.addWidget(self.error_details)

    def add_diagnostic(
        self, diagnostic: SqlDiagnostic, navigation_target: object | None = None
    ) -> None:
        """Add a SQL diagnostic message to the panel."""
        text = f"[{diagnostic.severity.upper()}] Line {diagnostic.start_line}: {diagnostic.message}"
        self._append_item(text, diagnostic.severity, navigation_target)

    def add_message(
        self,
        message: str,
        severity: str = "info",
        detail: str | None = None,
        navigation_target: object | None = None,
    ) -> None:
        """Add a general message with a severity role to the panel."""
        full_text = f"[{severity.upper()}] {message}"
        if detail:
            full_text += f"\n{detail}"
        self._append_item(full_text, severity, navigation_target)

    def show_query_result(
        self,
        result: QueryResult,
        clear_first: bool = True,
        navigation_target: object | None = None,
    ) -> None:
        """Surfaces execution status/errors/cancellations from a QueryResult."""
        if clear_first:
            self.clear_messages()
        if result.status is ExecutionStatus.FAILED:
            msg = f"Error ({result.error_type}): {result.error_message}"
            self.add_message(msg, severity="error", navigation_target=navigation_target)
            self.error_details_toggle.setVisible(bool(result.error_detail))
            self.error_details_toggle.setChecked(False)
            self.error_details.setPlainText(result.error_detail or "")
        elif result.status is ExecutionStatus.CANCELLED:
            self.add_message("Query execution cancelled.", severity="warning")
        elif result.status is ExecutionStatus.SUCCEEDED:
            self.add_message("Query executed successfully.", severity="info")

    def clear_messages(self) -> None:
        """Clear all messages from the panel."""
        self._list_widget.clear()
        self.error_details_toggle.setChecked(False)
        self.error_details_toggle.setVisible(False)
        self.error_details.clear()

    def message_count(self) -> int:
        """Return total message count."""
        return self._list_widget.count()

    def message_at(self, index: int) -> tuple[str, str]:
        """Return tuple of (message_text, severity_role) for item at index."""
        item = self._list_widget.item(index)
        if item is None:
            return ("", "")
        text = item.text()
        severity = str(item.data(Qt.ItemDataRole.UserRole) or "")
        return (text, severity)

    def _append_item(
        self, text: str, severity: str, navigation_target: object | None = None
    ) -> None:
        item = QListWidgetItem(text, self._list_widget)
        item.setData(Qt.ItemDataRole.UserRole, severity)
        item.setData(Qt.ItemDataRole.UserRole + 1, navigation_target)
        item.setForeground(QBrush(message_severity_color(severity, self.palette())))

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        if item is self._recently_activated_item:
            return
        navigation_target = item.data(Qt.ItemDataRole.UserRole + 1)
        if navigation_target is not None:
            self._recently_activated_item = item
            QTimer.singleShot(0, self._clear_recent_activation)
            self.diagnostic_activated.emit(navigation_target)

    def _clear_recent_activation(self) -> None:
        self._recently_activated_item = None
