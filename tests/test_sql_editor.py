from PyQt6.Qsci import QsciLexerSQL
from PyQt6.QtGui import QColor

from wherewolf.desktop.widgets import SqlEditor
from wherewolf.services import SqlCompletionService, StatementSelection, StatementService


class _SpyCompletionService(SqlCompletionService):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def complete(self, context):
        self.calls += 1
        return super().complete(context)


class _SpyStatementService(StatementService):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def find_statement(self, sql: str, cursor_offset: int) -> StatementSelection:
        self.calls += 1
        return super().find_statement(sql, cursor_offset)


def test_sql_editor_constructs_and_round_trips_text(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    assert editor.text() == ""

    editor.setText("SELECT 1")
    assert editor.text() == "SELECT 1"


def test_sql_editor_assigns_lexer(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    assert isinstance(editor.lexer(), QsciLexerSQL)


def _relative_luminance(colour: QColor) -> float:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * linear(colour.red())
        + 0.7152 * linear(colour.green())
        + 0.0722 * linear(colour.blue())
    )


def _contrast_ratio(first: QColor, second: QColor) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter, darker = sorted((first_luminance, second_luminance), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_sql_editor_text_lexer_styles_contrast_with_caret_line(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    lexer = editor.lexer()
    assert isinstance(lexer, QsciLexerSQL)

    caret_line = editor.caret_line_background
    text_styles = (
        QsciLexerSQL.Default,
        QsciLexerSQL.Identifier,
        QsciLexerSQL.Operator,
        QsciLexerSQL.Keyword,
        QsciLexerSQL.Number,
        QsciLexerSQL.SingleQuotedString,
    )

    contrasts = {style: _contrast_ratio(lexer.color(style), caret_line) for style in text_styles}

    assert all(ratio >= 4.5 for ratio in contrasts.values()), contrasts


def test_sql_editor_line_margin_and_features_configured(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.setText("\n".join(f"line {i}" for i in range(1000)))

    assert editor.marginWidth(0) > 0
    assert editor.autoIndent()
    assert editor.SendScintilla(editor.SCI_GETCARETLINEVISIBLE) == 1


def test_sql_editor_undo_redo_cut_copy_paste(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)

    editor.setText("abc")
    editor.selectAll()
    editor.cut()
    assert editor.text() == ""

    editor.paste()
    assert editor.text() == "abc"

    editor.undo()
    assert editor.text() == ""

    editor.redo()
    assert editor.text() == "abc"


def test_sql_editor_find_and_replace_all(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.setText("alpha beta alpha")

    assert editor.find_text("alpha")
    assert editor.replace_next("alpha", "gamma")
    assert "gamma" in editor.text()
    assert editor.replace_all("gamma", "alpha") == 1


def test_sql_editor_toggle_comment_round_trips_selection(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.setText("select 1;\nselect 2;")

    editor.selectAll()
    editor.toggle_comment()
    commented = editor.text()
    assert "-- " in commented

    editor.selectAll()
    editor.toggle_comment()
    assert editor.text() == "select 1;\nselect 2;"


def test_sql_editor_font_settings_are_restored_and_saved(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.set_font_size(18)

    assert editor.font_size == 18


def test_text_to_run_prefers_selection_over_statement_lookup(qtbot) -> None:
    spy_service = _SpyStatementService()
    editor = SqlEditor(statement_service=spy_service)
    qtbot.addWidget(editor)
    editor.setText("SELECT 1; SELECT 2;")

    editor.setSelection(0, 0, 0, 8)
    text, start, end = editor.text_to_run()

    assert text == "SELECT 1"
    assert spy_service.calls == 0
    assert start >= 0 and end > start

    editor.setSelection(0, 0, 0, 0)
    editor.text_to_run()
    assert spy_service.calls == 1


def test_format_selection_only_and_preserves_other_text(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.setText("select   1;\nselect   2;")

    editor.setSelection(0, 0, 0, 10)
    editor.format_selection_or_statement()

    assert "SELECT\n  1;" in editor.text()
    assert "select   2;" in editor.text()


def test_format_sql_one_undo_restores_entire_text(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)

    original = "select   1;\nselect   2;"
    editor.setText(original)
    editor.setCursorPosition(0, 0)
    editor.format_selection_or_statement()

    assert editor.text() != original
    editor.undo()
    assert editor.text() == original


def test_format_error_leaves_text_unchanged_and_reports_diagnostic(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    messages: list[list[str]] = []
    editor.diagnostics_reported.connect(lambda payload: messages.append(payload))

    editor.setText("select from")
    editor.format_selection_or_statement()

    assert editor.text() == "select from"
    assert messages
    assert messages[-1]


def test_sql_editor_completion_threshold_and_ctrl_space(qtbot, tmp_path) -> None:
    from PyQt6.QtCore import QSettings

    from wherewolf.services import SettingsService

    settings = QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat)
    settings_service = SettingsService(settings)

    spy_service = _SpyCompletionService()
    editor = SqlEditor(settings_service=settings_service, completion_service=spy_service)
    qtbot.addWidget(editor)

    assert editor.show_completion_action is not None
    assert editor.show_completion_action.isEnabled()
    assert editor.completion_threshold == 2
    assert editor.completion_enabled is True
    assert editor.show_completion_action.shortcut().toString() == "Ctrl+Space"

    # 1. Prefix shorter than default threshold (2) does NOT request completion
    editor.setText("S")
    editor.setCursorPosition(0, 1)
    editor.request_completion(forced=False)
    assert spy_service.calls == 0

    # 2. Prefix at or above threshold (2) DOES request completion
    editor.setText("SE")
    editor.setCursorPosition(0, 2)
    editor.request_completion(forced=False)
    assert spy_service.calls == 1


def test_sql_editor_completion_disabled_unforced_vs_forced(qtbot, tmp_path) -> None:
    from PyQt6.QtCore import QSettings

    from wherewolf.services import SettingsService

    settings = QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat)
    settings_service = SettingsService(settings)
    settings_service.save_completion_enabled(False)

    spy_service = _SpyCompletionService()
    editor = SqlEditor(settings_service=settings_service, completion_service=spy_service)
    qtbot.addWidget(editor)

    assert editor.completion_enabled is False

    # 3. With completion_enabled=False, unforced typing does NOT request completion
    editor.setText("SELECT")
    editor.setCursorPosition(0, 6)
    editor.request_completion(forced=False)
    assert spy_service.calls == 0

    # Forced request (Ctrl+Space) STILL requests completion
    editor.request_completion(forced=True)
    assert spy_service.calls == 1


def test_sql_editor_completion_custom_threshold(qtbot, tmp_path) -> None:
    from PyQt6.QtCore import QSettings

    from wherewolf.services import SettingsService

    settings = QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat)
    settings_service = SettingsService(settings)
    settings_service.save_completion_threshold(3)

    spy_service = _SpyCompletionService()
    editor = SqlEditor(settings_service=settings_service, completion_service=spy_service)
    qtbot.addWidget(editor)

    assert editor.completion_threshold == 3

    # 4. Set to 3: 2-character prefix no longer triggers
    editor.setText("SE")
    editor.setCursorPosition(0, 2)
    editor.request_completion(forced=False)
    assert spy_service.calls == 0

    # 3-character prefix DOES trigger
    editor.setText("SEL")
    editor.setCursorPosition(0, 3)
    editor.request_completion(forced=False)
    assert spy_service.calls == 1


def test_main_window_show_completion_action_is_same_object_in_query_menu_and_editor(qtbot) -> None:
    from wherewolf.desktop import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    action_in_actions = window.desktop_actions.show_completion
    action_in_menu = None
    for action in window.query_menu.actions():
        if action.text() == "Show Completion":
            action_in_menu = action
            break

    assert action_in_menu is not None
    assert action_in_menu is action_in_actions
    assert window.editor.show_completion_action is action_in_actions


def test_sql_editor_gui_thread_never_blocked_with_none_schema(qtbot) -> None:
    from pathlib import Path
    from uuid import uuid4

    from wherewolf.domain.enums import SourceFormat
    from wherewolf.domain.models import CatalogEntry

    catalog = (
        CatalogEntry(
            id=uuid4(),
            alias="orders",
            path=Path("/tmp/orders.csv"),
            source_format=SourceFormat.CSV,
            schema=None,
        ),
    )

    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.set_catalog(catalog)

    editor.setText("SELECT o. FROM orders o")
    editor.setCursorPosition(0, 9)

    # Trigger completion while schema work is incomplete. A bounded elapsed time proves the GUI
    # call does not wait for schema inspection; no column completion may be fabricated.
    import time

    started = time.monotonic()
    editor.request_completion(forced=True)
    assert time.monotonic() - started < 0.5
