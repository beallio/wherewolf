from datetime import UTC, datetime
from uuid import uuid4

from pytestqt.qtbot import QtBot

from wherewolf.desktop.widgets.messages_panel import MessagesPanel
from wherewolf.domain.enums import ExecutionStatus
from wherewolf.domain.models import QueryResult, SqlDiagnostic


def test_messages_panel_add_diagnostic(qtbot: QtBot) -> None:
    panel = MessagesPanel()
    qtbot.addWidget(panel)

    diag = SqlDiagnostic(
        message="Syntax error at line 1", severity="error", start_line=1, start_column=1
    )
    panel.add_diagnostic(diag)

    assert panel.message_count() == 1
    msg, severity = panel.message_at(0)
    assert "Syntax error at line 1" in msg
    assert severity == "error"


def test_messages_panel_show_execution_error(qtbot: QtBot) -> None:
    panel = MessagesPanel()
    qtbot.addWidget(panel)

    result = QueryResult(
        request_id=uuid4(),
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.05,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="TableNotFoundError",
        error_message="Table 'users' not found",
    )
    panel.show_query_result(result)

    assert panel.message_count() >= 1
    msg, severity = panel.message_at(0)
    assert "TableNotFoundError" in msg
    assert "Table 'users' not found" in msg
    assert severity == "error"


def test_messages_panel_show_execution_cancelled(qtbot: QtBot) -> None:
    panel = MessagesPanel()
    qtbot.addWidget(panel)

    result = QueryResult(
        request_id=uuid4(),
        status=ExecutionStatus.CANCELLED,
        frame=None,
        execution_seconds=0.01,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
    )
    panel.show_query_result(result)

    assert panel.message_count() >= 1
    msg, severity = panel.message_at(0)
    assert "cancelled" in msg.lower()
    assert severity in ("cancelled", "warning")
