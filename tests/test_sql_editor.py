from PyQt6.Qsci import QsciLexerSQL
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor, QKeySequence
from PyQt6.QtTest import QTest

from wherewolf.desktop.widgets import SqlEditor
from wherewolf.domain import SqlDiagnostic
from wherewolf.services import (
    SettingsService,
    SqlCompletionService,
    StatementSelection,
    StatementService,
)


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


class _DiagnosticSpyEditor(SqlEditor):
    def __init__(self) -> None:
        super().__init__()
        self.diagnostic_fills: list[tuple[int, int, int, int, int]] = []
        self.diagnostic_clears: list[tuple[int, int, int, int, int]] = []
        self.diagnostic_focus_calls = 0

    def fillIndicatorRange(
        self,
        lineFrom: int,
        indexFrom: int,
        lineTo: int,
        indexTo: int,
        indicatorNumber: int,
    ) -> None:
        self.diagnostic_fills.append((lineFrom, indexFrom, lineTo, indexTo, indicatorNumber))
        super().fillIndicatorRange(lineFrom, indexFrom, lineTo, indexTo, indicatorNumber)

    def clearIndicatorRange(
        self,
        lineFrom: int,
        indexFrom: int,
        lineTo: int,
        indexTo: int,
        indicatorNumber: int,
    ) -> None:
        self.diagnostic_clears.append((lineFrom, indexFrom, lineTo, indexTo, indicatorNumber))
        super().clearIndicatorRange(lineFrom, indexFrom, lineTo, indexTo, indicatorNumber)

    def setFocus(self, reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason) -> None:
        self.diagnostic_focus_calls += 1
        super().setFocus(reason)


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


def test_sql_editor_themes_are_complete_and_have_distinct_papers(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    assert set(editor.THEME_NAMES) == set(editor._THEMES)
    assert all(len(colours) == 5 for colours in editor._THEMES.values())

    paper_colours: list[str] = []
    for theme in editor.THEME_NAMES:
        editor.set_theme(theme)
        paper_colours.append(editor._PAPER.name())

    assert len(set(paper_colours)) == len(editor.THEME_NAMES)


def test_sql_editor_exposes_additional_complete_themes(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)

    assert len(editor.THEME_NAMES) >= 7
    assert all(len(editor._THEMES[name]) == 5 for name in editor.THEME_NAMES)


def test_sql_editor_new_theme_persists_and_unknown_theme_is_ignored(qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "theme-round-trip.ini"), QSettings.Format.IniFormat)
    settings_service = SettingsService(settings)
    editor = SqlEditor(settings_service=settings_service)
    qtbot.addWidget(editor)

    editor.set_theme("Solarized Dark")
    assert editor.theme_name == "Solarized Dark"
    restored = SqlEditor(settings_service=settings_service)
    qtbot.addWidget(restored)
    assert restored.theme_name == "Solarized Dark"

    restored.set_theme("Not a real theme")
    assert restored.theme_name == "Solarized Dark"


def test_sql_editor_line_margin_and_features_configured(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.setText("\n".join(f"line {i}" for i in range(1000)))

    assert editor.marginWidth(0) > 0
    assert editor.autoIndent()
    assert editor.SendScintilla(editor.SCI_GETCARETLINEVISIBLE) == 1


def test_sql_editor_horizontal_scrollbar_tracks_line_width(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.resize(320, 160)
    editor.show()
    scrollbar = editor.horizontalScrollBar()
    assert scrollbar is not None

    editor.setText("SELECT 1")
    qtbot.waitUntil(lambda: not scrollbar.isVisible(), timeout=1000)

    editor.setText("x" * 1000)
    qtbot.waitUntil(scrollbar.isVisible, timeout=1000)


def test_sql_editor_horizontal_scroll_width_shrinks_after_replacement(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.resize(320, 160)
    editor.show()

    editor.setText("x" * 1000)
    qtbot.waitUntil(lambda: editor.SendScintilla(editor.SCI_GETSCROLLWIDTH) > 1000)
    long_width = editor.SendScintilla(editor.SCI_GETSCROLLWIDTH)

    editor.setText("SELECT 1")
    qtbot.waitUntil(lambda: editor.SendScintilla(editor.SCI_GETSCROLLWIDTH) < long_width / 2)
    assert editor.SendScintilla(editor.SCI_GETSCROLLWIDTH) < long_width / 2


def test_sql_editor_typing_mid_line_keeps_horizontal_scroll_position(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.resize(320, 160)
    editor.show()
    editor.setText("x" * 1000)
    scrollbar = editor.horizontalScrollBar()
    assert scrollbar is not None
    qtbot.waitUntil(lambda: scrollbar.maximum() > 0)

    scrollbar.setValue(scrollbar.maximum() // 2)
    before = scrollbar.value()
    editor.setCursorPosition(0, 500)
    editor.insert("y")

    assert before > 0
    assert scrollbar.value() > 0


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


def test_sql_editor_replace_all_is_undoable(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.setText("alpha beta alpha")
    editor.setCursorPosition(0, len(editor.text()))
    editor.insert("!")

    assert editor.replace_all("alpha", "gamma") == 2
    assert editor.text() == "gamma beta gamma!"

    editor.undo()

    assert editor.text() == "alpha beta alpha!"


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


def test_sql_editor_toggle_comment_preserves_selected_line_range_for_round_trip(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    original = "select 1;\nselect 2;"
    editor.setText(original)
    editor.setSelection(0, 0, 1, len("select 2;"))

    editor.toggle_comment()

    assert editor.text() == "-- select 1;\n-- select 2;"
    assert editor.getSelection() == (0, 0, 1, len("-- select 2;"))

    editor.toggle_comment()

    assert editor.text() == original


def test_sql_editor_toggle_comment_round_trips_mid_document_selected_lines(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    original = "select 1;\nselect 2;\nselect 3;"
    editor.setText(original)
    editor.setSelection(0, 0, 1, len("select 2;"))

    editor.toggle_comment()

    assert editor.text() == "-- select 1;\n-- select 2;\nselect 3;"
    assert editor.getSelection() == (0, 0, 1, len("-- select 2;"))

    editor.toggle_comment()

    assert editor.text() == original


def test_sql_editor_toggle_comment_one_undo_restores_original_text(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    original = "select 1;\nselect 2;"
    editor.setText(original)
    editor.selectAll()

    editor.toggle_comment()

    assert editor.isUndoAvailable() is True
    editor.undo()
    assert editor.text() == original


def test_sql_editor_ctrl_slash_toggles_comment_without_inserting_stray_slash(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.show()
    QTest.qWaitForWindowExposed(editor)  # ty: ignore[no-matching-overload]  # QTest stubs model self.
    editor.setFocus()
    editor.setText("select 1")

    QTest.keyClick(  # ty: ignore[no-matching-overload]  # QTest stubs model self.
        editor,
        Qt.Key.Key_Slash,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert editor.text() == "-- select 1"
    assert "/" not in editor.text()


def test_sql_editor_font_settings_are_restored_and_saved(qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "font-preferences.ini"), QSettings.Format.IniFormat)
    settings_service = SettingsService(settings)
    editor = SqlEditor(settings_service=settings_service)
    qtbot.addWidget(editor)
    editor.set_font_size(28)

    lexer = editor.lexer()
    assert isinstance(lexer, QsciLexerSQL)
    for style in (QsciLexerSQL.Default, QsciLexerSQL.Keyword, QsciLexerSQL.Identifier):
        assert lexer.font(style).pointSize() == 28
    assert editor.font().pointSize() == 28
    assert editor.font_size == 28
    assert settings_service.restore_editor_font_size() == 28

    restored = SqlEditor(settings_service=settings_service)
    qtbot.addWidget(restored)
    restored_lexer = restored.lexer()
    assert isinstance(restored_lexer, QsciLexerSQL)
    for style in (QsciLexerSQL.Default, QsciLexerSQL.Keyword, QsciLexerSQL.Identifier):
        assert restored_lexer.font(style).pointSize() == 28


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


def test_show_diagnostic_moves_focuses_and_marks_a_visible_range(qtbot) -> None:
    editor = _DiagnosticSpyEditor()
    qtbot.addWidget(editor)
    editor.setText("SELECT 1\nmissing_column")
    editor.show()

    editor.show_diagnostic(SqlDiagnostic("missing column", "error", 2, 1))

    assert editor.getCursorPosition() == (1, 0)
    assert editor.diagnostic_focus_calls == 1
    assert editor.diagnostic_fills
    start_line, start_column, end_line, end_column, _indicator = editor.diagnostic_fills[-1]
    assert (start_line, start_column) == (1, 0)
    assert end_line == 1
    assert end_column > start_column


def test_show_diagnostic_clamps_out_of_range_coordinates(qtbot) -> None:
    editor = _DiagnosticSpyEditor()
    qtbot.addWidget(editor)
    editor.setText("first\nlast")

    editor.show_diagnostic(SqlDiagnostic("bad position", "error", 99, 99))

    assert editor.getCursorPosition() == (1, 4)
    assert editor.diagnostic_fills[-1][0:4] == (1, 3, 1, 4)


def test_show_diagnostic_declines_ambiguous_unicode_columns(qtbot) -> None:
    editor = _DiagnosticSpyEditor()
    qtbot.addWidget(editor)
    editor.setText("SELECT café missing")
    editor.setCursorPosition(0, 0)

    editor.show_diagnostic(SqlDiagnostic("missing column", "error", 1, 13))

    assert editor.getCursorPosition() == (0, 0)
    assert not editor.diagnostic_fills


def test_diagnostics_clear_when_editor_text_changes_and_are_idempotent(qtbot) -> None:
    editor = _DiagnosticSpyEditor()
    qtbot.addWidget(editor)
    editor.setText("SELECT missing_column")
    editor.show_diagnostic(SqlDiagnostic("missing column", "error", 1, 8))
    clear_count_before_change = len(editor.diagnostic_clears)

    editor.setText("SELECT repaired_column")
    clear_count_after_change = len(editor.diagnostic_clears)
    editor.clear_diagnostics()
    editor.clear_diagnostics()

    assert clear_count_after_change > clear_count_before_change
    assert len(editor.diagnostic_clears) == clear_count_after_change + 2


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


def test_sql_editor_typing_shows_catalog_keyword_and_function_completions(qtbot) -> None:
    from pathlib import Path
    from uuid import uuid4

    from wherewolf.domain.enums import SourceFormat
    from wherewolf.domain.models import CatalogEntry

    editor = SqlEditor()
    qtbot.addWidget(editor)
    editor.set_catalog(
        (
            CatalogEntry(
                id=uuid4(),
                alias="customers",
                path=Path("customers.csv"),
                source_format=SourceFormat.CSV,
                schema=(),
            ),
        )
    )
    editor.show()
    editor.setFocus()
    qtbot.keyClicks(editor, "SELECT * FROM ")
    qtbot.keyClicks(editor, "cus")

    qtbot.waitUntil(editor.isListActive)
    assert "customers" in editor._completion_adapter._active_items

    editor.cancelList()
    editor.setText("SELECT ")
    editor.setCursorPosition(0, 7)
    editor.setFocus()
    editor.request_completion(forced=True)
    qtbot.waitUntil(editor.isListActive)
    assert "SELECT" in editor._completion_adapter._active_items
    assert "COUNT" in editor._completion_adapter._active_items


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


def test_sql_editor_releases_scintilla_keys_that_collide_with_app_shortcuts(qtbot) -> None:
    editor = SqlEditor()
    qtbot.addWidget(editor)

    commands = editor.standardCommands()
    for sequence in ("Ctrl+T", "Ctrl+/"):
        key = QKeySequence(sequence)[0].toCombined()
        assert commands.boundTo(key) is None, f"{sequence} is still bound in Scintilla"
