"""QScintilla SQL editor used by the desktop shell."""

from __future__ import annotations

from typing import ClassVar

from PyQt6.Qsci import QsciLexerSQL, QsciScintilla
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QFontMetrics, QKeySequence
from PyQt6.QtWidgets import QMenu, QWidget

from wherewolf.desktop.widgets.completion_adapter import CompletionAdapter
from wherewolf.domain import CatalogEntry, SqlDiagnostic
from wherewolf.domain.models import CompletionContext
from wherewolf.services import (
    SettingsService,
    SqlCompletionService,
    SqlFormattingService,
    StatementService,
)
from wherewolf.services.completion_context import detect_context


class SqlEditor(QsciScintilla):
    """QScintilla-based SQL editor with minimal desktop actions."""

    diagnostics_reported = pyqtSignal(list)
    THEME_NAMES = ("Dark", "Light")
    _THEMES: ClassVar[dict[str, tuple[str, str, str, str, str]]] = {
        "Dark": ("#1E1E1E", "#D4D4D4", "#569CD6", "#B5CEA8", "#CE9178"),
        "Light": ("#FFFFFF", "#202020", "#003D99", "#005F5F", "#8B2F00"),
    }

    def __init__(
        self,
        *,
        settings_service: SettingsService | None = None,
        statement_service: StatementService | None = None,
        formatting_service: SqlFormattingService | None = None,
        completion_service: SqlCompletionService | None = None,
        format_action: QAction | None = None,
        show_completion_action: QAction | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self._settings_service = settings_service or SettingsService()
        self._statement_service = statement_service or StatementService()
        self._formatting_service = formatting_service or SqlFormattingService()
        self._completion_service = completion_service or SqlCompletionService()
        self._format_action = format_action

        if show_completion_action is not None:
            self._show_completion_action = show_completion_action
        else:
            self._show_completion_action = QAction("Show Completion", self)
            self._show_completion_action.setShortcut(QKeySequence("Ctrl+Space"))
            self._show_completion_action.setEnabled(True)

        self._catalog: tuple[CatalogEntry, ...] = ()
        self._completion_adapter = CompletionAdapter(self, self._completion_service)
        self._diagnostic_indicator = 1
        self._font_size = self._settings_service.restore_editor_font_size()
        self._theme_name = self._settings_service.restore_editor_theme()
        if self._theme_name not in self._THEMES:
            self._theme_name = SettingsService.DEFAULT_EDITOR_THEME
        self._set_theme_colours(self._theme_name)

        self._setup_editor()
        self._setup_actions()
        self._setup_context_menu()
        self._setup_settings()
        self._refresh_line_margin()
        self.textChanged.connect(self._refresh_line_margin)
        self.textChanged.connect(self._on_text_changed_completion)
        self._show_completion_action.triggered.connect(lambda: self.request_completion(forced=True))

    @property
    def font_size(self) -> int:
        return self._font_size

    @property
    def show_completion_action(self) -> QAction:
        return self._show_completion_action

    @property
    def edit_actions(self) -> tuple[QAction, QAction, QAction, QAction, QAction, QAction]:
        """Return the editor-owned actions suitable for an Edit menu."""
        return (
            self._undo_action,
            self._redo_action,
            self._cut_action,
            self._copy_action,
            self._paste_action,
            self._toggle_comment_action,
        )

    @property
    def completion_threshold(self) -> int:
        return self._settings_service.restore_completion_threshold()

    @property
    def completion_enabled(self) -> bool:
        return self._settings_service.restore_completion_enabled()

    @property
    def caret_line_background(self) -> QColor:
        """Return the rendered caret-line background colour."""
        return QColor(self._caret_line_background)

    @property
    def theme_name(self) -> str:
        return self._theme_name

    def set_catalog(self, catalog: tuple[CatalogEntry, ...]) -> None:
        self._catalog = tuple(catalog)

    def request_completion(self, forced: bool = False) -> None:
        text = self.text()
        line, col = self.getCursorPosition()
        cursor_offset = self.positionFromLineIndex(line, col)

        if not forced:
            if not self.completion_enabled:
                return
            cursor_ctx = detect_context(text, cursor_offset)
            if len(cursor_ctx.prefix) < self.completion_threshold:
                return

        ctx = CompletionContext(
            sql=text,
            cursor_offset=cursor_offset,
            dialect="duckdb",
            catalog=self._catalog,
        )
        call_tip = self._completion_service.call_tip(ctx)
        if call_tip:
            self.SendScintilla(self.SCI_CALLTIPSHOW, cursor_offset, call_tip.encode())
        self._completion_adapter.request_completion(ctx)

    def _on_text_changed_completion(self) -> None:
        self.request_completion(forced=False)

    def _setup_editor(self) -> None:
        lexer = QsciLexerSQL(self)
        self._apply_lexer_colours(lexer)
        self.setLexer(lexer)
        self.setPaper(self._PAPER)
        self.setColor(self._TEXT)
        self.setAutoIndent(True)
        self.setAutoCompletionShowSingle(True)
        self.setIndentationGuides(True)
        self.setIndentationWidth(2)
        self.setTabWidth(2)
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setCaretLineVisible(True)
        self._caret_line_background = lexer.paper(QsciLexerSQL.Default).lighter(115)
        self.setCaretLineBackgroundColor(self._caret_line_background)
        self.setCaretForegroundColor(self._TEXT)
        self._apply_margin_colours()
        self.setMarginLineNumbers(0, True)
        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)

        self.indicatorDefine(
            QsciScintilla.IndicatorStyle.SquiggleIndicator,
            self._diagnostic_indicator,
        )
        self.setIndicatorForegroundColor(QColor("#d7191c"), self._diagnostic_indicator)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._undo_action.triggered.connect(self.undo)

        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._redo_action.triggered.connect(self.redo)

        self._cut_action = QAction("Cut", self)
        self._cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        self._cut_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._cut_action.triggered.connect(self.cut)

        self._copy_action = QAction("Copy", self)
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self._copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._copy_action.triggered.connect(self.copy)

        self._paste_action = QAction("Paste", self)
        self._paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self._paste_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._paste_action.triggered.connect(self.paste)

        self._toggle_comment_action = QAction("Toggle Comment", self)
        self._toggle_comment_action.setShortcut(QKeySequence("Ctrl+/"))
        self._toggle_comment_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._toggle_comment_action.triggered.connect(self.toggle_comment)

        if self._format_action is not None:
            self._format_action.triggered.connect(self.format_selection_or_statement)

    def _apply_lexer_colours(self, lexer: QsciLexerSQL) -> None:
        """Apply explicit text and paper colours for every SQL lexer style."""
        for style in range(QsciLexerSQL.Default, QsciLexerSQL.QuotedOperator + 1):
            lexer.setColor(self._TEXT, style)
            lexer.setPaper(self._PAPER, style)
        lexer.setDefaultColor(self._TEXT)
        lexer.setDefaultPaper(self._PAPER)
        lexer.setColor(self._KEYWORD, QsciLexerSQL.Keyword)
        lexer.setColor(self._KEYWORD, QsciLexerSQL.PlusKeyword)
        lexer.setColor(self._NUMBER, QsciLexerSQL.Number)
        lexer.setColor(self._STRING, QsciLexerSQL.SingleQuotedString)
        lexer.setColor(self._STRING, QsciLexerSQL.DoubleQuotedString)

    def _set_theme_colours(self, theme: str) -> None:
        paper, text, keyword, number, string = self._THEMES[theme]
        self._PAPER = QColor(paper)
        self._TEXT = QColor(text)
        self._KEYWORD = QColor(keyword)
        self._NUMBER = QColor(number)
        self._STRING = QColor(string)

    def set_theme(self, theme: str) -> None:
        """Apply and persist a supported editor colour theme."""
        if theme not in self._THEMES:
            return
        self._theme_name = theme
        self._set_theme_colours(theme)
        lexer = self.lexer()
        if isinstance(lexer, QsciLexerSQL):
            self._apply_lexer_colours(lexer)
            self._caret_line_background = lexer.paper(QsciLexerSQL.Default).lighter(115)
            self.setCaretLineBackgroundColor(self._caret_line_background)
        self.setPaper(self._PAPER)
        self.setColor(self._TEXT)
        self.setCaretForegroundColor(self._TEXT)
        self._apply_margin_colours()
        self._settings_service.save_editor_theme(theme)

    def _apply_margin_colours(self) -> None:
        """Blend line numbers with the editor paper and caret-line treatment."""
        self.setMarginsBackgroundColor(self._PAPER.lighter(115))
        self.setMarginsForegroundColor(self._TEXT)

    def _setup_actions(self) -> None:
        self.setCaretLineVisible(True)

    def _setup_context_menu(self) -> None:
        return

    def _setup_settings(self) -> None:
        self._apply_font_size(self._font_size)

    def _apply_font_size(self, size: int) -> None:
        size = max(6, min(int(size), 64))
        self._font_size = size

        font = self.font()
        if isinstance(font, QFont):
            font.setPointSize(size)
            QWidget.setFont(self, font)

        lexer = self.lexer()
        if isinstance(lexer, QsciLexerSQL):
            lexer_font = lexer.defaultFont(0)
            if isinstance(lexer_font, QFont):
                lexer_font.setPointSize(size)
                lexer.setDefaultFont(lexer_font)
            lexer.setFont(font)

        self._refresh_line_margin()

    def _refresh_line_margin(self) -> None:
        line_count = max(self.lines(), 1)
        digit_count = len(str(line_count))
        metrics = QFontMetrics(self.font())
        digit_width = metrics.horizontalAdvance("9" * digit_count)
        padding = metrics.horizontalAdvance("9")
        self.setMarginWidth(0, digit_width + padding)

    def _update_status(self, message: str | None = None) -> None:
        if message is None:
            self.diagnostics_reported.emit(())
        else:
            self.diagnostics_reported.emit(
                (
                    SqlDiagnostic(
                        message=message,
                        severity="info",
                        start_line=1,
                        start_column=1,
                    ),
                )
            )

    def set_font_size(self, size: int) -> None:
        self._apply_font_size(size)
        self._settings_service.save_editor_font_size(self._font_size)

    def text_to_run(self) -> tuple[str, int, int]:
        selected = self._selected_text_range()
        if selected is not None:
            return selected

        cursor_line, cursor_column = self.getCursorPosition()
        cursor = self.positionFromLineIndex(cursor_line, cursor_column)
        text = self.text()
        if cursor > 0 and cursor >= len(text):
            cursor = len(text) - 1
        selection = self._statement_service.find_statement(text, cursor)
        if selection.text is None:
            self._update_status(selection.reason)
            return "", -1, -1

        return (
            selection.text,
            selection.start_offset,
            selection.end_offset,
        )

    def _selected_text_range(self) -> tuple[str, int, int] | None:
        if not self.hasSelectedText():
            return None

        start_line, start_col, end_line, end_col = self.getSelection()
        if (start_line, start_col) == (end_line, end_col):
            return None

        start = self.positionFromLineIndex(start_line, start_col)
        end = self.positionFromLineIndex(end_line, end_col)
        return self.selectedText(), start, end

    def format_selection_or_statement(self) -> None:
        text, start, end = self.text_to_run()
        if not text or start < 0 or end < 0:
            return

        cursor_line, cursor_column = self.getCursorPosition()
        visible_line = self.firstVisibleLine()
        horizontal_bar = self.horizontalScrollBar()
        horizontal = horizontal_bar.value() if horizontal_bar is not None else 0

        result = self._formatting_service.format_sql(text, dialect="duckdb")
        self._clear_diagnostic_indicator()

        if result.diagnostics:
            self._show_parse_diagnostic(result.diagnostics[0])
            self._update_status(result.diagnostics[0].message)
            return

        if result.formatted_sql is None or result.formatted_sql == text:
            self._update_status()
            return

        start_line, start_col = self.lineIndexFromPosition(start)
        end_line, end_col = self.lineIndexFromPosition(end)

        self.beginUndoAction()
        try:
            self.setSelection(start_line, start_col, end_line, end_col)
            self.replaceSelectedText(result.formatted_sql)
            self.setCursorPosition(cursor_line, cursor_column)
            self._restore_view(visible_line, horizontal)
            self._update_status()
        finally:
            self.endUndoAction()

    def _show_parse_diagnostic(self, diagnostic: SqlDiagnostic) -> None:
        line = max(diagnostic.start_line - 1, 0)
        line_count = max(self.lines(), 1)
        if line >= line_count:
            line = line_count - 1

        line_text = self.text(line)
        start_column = max(diagnostic.start_column - 1, 0)
        end_column = max(min(start_column + 1, max(len(line_text), 1)), 1)
        try:
            self.fillIndicatorRange(
                line,
                min(start_column, len(line_text)),
                line,
                min(end_column, max(len(line_text), 1)),
                self._diagnostic_indicator,
            )
        except Exception:  # noqa: BLE001
            return

    def _clear_diagnostic_indicator(self) -> None:
        line_count = max(self.lines(), 1)
        try:
            self.clearIndicatorRange(
                0,
                0,
                line_count - 1,
                max(self.lineLength(line_count - 1), 1),
                self._diagnostic_indicator,
            )
        except Exception:  # noqa: BLE001
            return

    def _restore_view(self, first_visible_line: int, horizontal: int) -> None:
        self.setFirstVisibleLine(max(0, first_visible_line))
        horizontal_bar = self.horizontalScrollBar()
        if horizontal_bar is not None:
            horizontal_bar.setValue(horizontal)

    def toggle_comment(self) -> None:
        line_start, line_end = self._selected_or_current_line_range()
        text = self.text()
        if not text:
            return

        lines = text.splitlines(keepends=True)
        if not lines:
            return

        for index in range(line_start - 1, line_end):
            if index >= len(lines):
                break
            line = lines[index]
            stripped = line.lstrip(" \t")
            indent = line[: len(line) - len(stripped)]
            if stripped.startswith("-- "):
                lines[index] = f"{indent}{stripped[3:]}"
            elif stripped.startswith("--"):
                lines[index] = f"{indent}{stripped[2:].lstrip()}"
            else:
                lines[index] = f"{indent}-- {stripped}"

        self.setText("".join(lines))

    def _selected_or_current_line_range(self) -> tuple[int, int]:
        if self.hasSelectedText():
            start_line, _, end_line, _ = self.getSelection()
            return start_line + 1, end_line + 1

        cursor_line, _ = self.getCursorPosition()
        return cursor_line + 1, cursor_line + 1

    def insert_text(self, value: str) -> None:
        self.insert(value)

    def find_text(self, value: str) -> bool:
        return self.findFirst(value, False, False, False, False, True, 0, 0)

    def replace_next(self, old_text: str, new_text: str) -> bool:
        if not self.find_text(old_text):
            return False
        self.replaceSelectedText(new_text)
        return True

    def replace_all(self, old_text: str, new_text: str) -> int:
        current = self.text()
        replaced = current.replace(old_text, new_text)
        if current == replaced:
            return 0

        self.setText(replaced)
        return current.count(old_text)

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        menu.addAction(self._undo_action)
        menu.addAction(self._redo_action)
        menu.addSeparator()
        menu.addAction(self._cut_action)
        menu.addAction(self._copy_action)
        menu.addAction(self._paste_action)
        menu.addSeparator()
        menu.addAction(self._toggle_comment_action)
        menu.addSeparator()
        menu.addAction(self._show_completion_action)
        if self._format_action is not None:
            menu.addSeparator()
            menu.addAction(self._format_action)

        menu.exec(self.mapToGlobal(position))
