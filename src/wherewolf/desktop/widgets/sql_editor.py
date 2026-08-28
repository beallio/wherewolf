"""QScintilla SQL editor used by the desktop shell."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from PyQt6.Qsci import QsciLexerSQL, QsciScintilla
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QFontMetrics, QKeyEvent, QKeySequence
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
from wherewolf.services.text_case import transform_lines

_TOGGLE_COMMENT_SHORTCUT = QKeySequence("Ctrl+/")

# QScintilla accepts the ShortcutOverride event for every key in its own command set,
# which cancels Qt's shortcut dispatch before the application actions ever see it.
# These sequences belong to desktop actions ("New Tab", "Toggle Comment"), so their
# Scintilla bindings are released when the editor is set up.
_RELEASED_SCINTILLA_SHORTCUTS = (
    "Ctrl+T",
    _TOGGLE_COMMENT_SHORTCUT.toString(),
    "Ctrl+U",
    "Ctrl+Shift+U",
)


class SqlEditor(QsciScintilla):
    """QScintilla-based SQL editor with minimal desktop actions."""

    diagnostics_reported = pyqtSignal(list)
    THEME_NAMES = (
        "Dark",
        "Light",
        "Solarized Dark",
        "Solarized Light",
        "High Contrast",
        "Monokai",
        "Nord",
    )
    _THEMES: ClassVar[dict[str, tuple[str, str, str, str, str]]] = {
        "Dark": ("#1E1E1E", "#D4D4D4", "#569CD6", "#B5CEA8", "#CE9178"),
        "Light": ("#FFFFFF", "#202020", "#003D99", "#005F5F", "#8B2F00"),
        "Solarized Dark": ("#002B36", "#839496", "#268BD2", "#B58900", "#2AA198"),
        "Solarized Light": ("#FDF6E3", "#657B83", "#268BD2", "#B58900", "#2AA198"),
        "High Contrast": ("#000000", "#FFFFFF", "#00FFFF", "#FFFF00", "#00FF00"),
        "Monokai": ("#272822", "#F8F8F2", "#F92672", "#AE81FF", "#E6DB74"),
        "Nord": ("#2E3440", "#D8DEE9", "#88C0D0", "#B48EAD", "#A3BE8C"),
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
        bind_shared_actions: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self._settings_service = settings_service or SettingsService()
        self._statement_service = statement_service or StatementService()
        self._formatting_service = formatting_service or SqlFormattingService()
        self._completion_service = completion_service or SqlCompletionService()
        self._format_action = format_action
        self._bind_shared_actions = bind_shared_actions

        if show_completion_action is not None:
            self._show_completion_action = show_completion_action
        else:
            self._show_completion_action = QAction("Show Completion", self)
            self._show_completion_action.setShortcut(QKeySequence("Ctrl+Space"))
            self._show_completion_action.setEnabled(True)

        self._catalog: tuple[CatalogEntry, ...] = ()
        self._completion_dialect = "duckdb"
        self._completion_insertion_in_progress = False
        self._completion_updates_suspended = False
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
        self.textChanged.connect(self.clear_diagnostics)
        if show_completion_action is None or self._bind_shared_actions:
            self._show_completion_action.triggered.connect(
                lambda: self.request_completion(forced=True)
            )

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

    def set_completion_dialect(self, dialect: str) -> None:
        """Use an execution-engine completion catalog for future requests."""

        normalized = dialect.strip().lower()
        if normalized not in {"duckdb", "spark"}:
            raise ValueError(f"Unsupported completion dialect: {dialect}")
        self._completion_dialect = normalized

    def setText(self, text: str) -> None:
        """Replace the document and let scroll-width tracking recompute from scratch.

        QScintilla's tracking only expands its cached width.  Resetting only for
        wholesale replacements avoids changing the horizontal scroll position on every
        character typed into an existing line.
        """
        completion_adapter = getattr(self, "_completion_adapter", None)
        if completion_adapter is not None:
            completion_adapter.cancel()
        self._completion_updates_suspended = True
        try:
            super().setText(text)
        finally:
            self._completion_updates_suspended = False
        self.setScrollWidth(1)

    def set_text_undoable(self, text: str) -> None:
        """Replace the document while allowing one undo to restore its prior contents."""
        self.beginUndoAction()
        try:
            self.selectAll(True)
            self.replaceSelectedText(text)
        finally:
            self.endUndoAction()
        self.setScrollWidth(1)

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
            dialect=self._completion_dialect,
            catalog=self._catalog,
        )
        call_tip = self._completion_service.call_tip(ctx)
        if call_tip:
            self.SendScintilla(self.SCI_CALLTIPSHOW, cursor_offset, call_tip.encode())
        self._completion_adapter.request_completion(ctx)

    def _on_text_changed_completion(self) -> None:
        if self._completion_insertion_in_progress or self._completion_updates_suspended:
            return
        self.request_completion(forced=False)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """Return printable typing to the document before refreshing a user list.

        An empty ``QKeyEvent.text()`` is "printable" in Python, so the emptiness check is
        load-bearing: without it every arrow, page and Home/End key cancels the active user
        list before QScintilla can navigate or accept it.
        """

        text = e.text()
        if text and text.isprintable() and self.isListActive():
            self._completion_adapter.cancel()
        super().keyPressEvent(e)

    def _set_completion_insertion_in_progress(self, active: bool) -> None:
        """Keep an inserted completion from recursively reopening a stale user list."""

        self._completion_insertion_in_progress = active

    def _release_conflicting_scintilla_keys(self) -> None:
        """Unbind Scintilla commands whose keys belong to desktop actions."""
        commands = self.standardCommands()
        for sequence in _RELEASED_SCINTILLA_SHORTCUTS:
            key = QKeySequence(sequence)[0].toCombined()
            command = commands.boundTo(key)
            if command is None:
                continue
            if command.key() == key:
                command.setKey(0)
            if command.alternateKey() == key:
                command.setAlternateKey(0)

    def _setup_editor(self) -> None:
        self._release_conflicting_scintilla_keys()

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
        self.setScrollWidth(1)
        self.setScrollWidthTracking(True)

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
        self._toggle_comment_action.setShortcut(_TOGGLE_COMMENT_SHORTCUT)
        self._toggle_comment_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._toggle_comment_action.triggered.connect(self.toggle_comment)
        self.addAction(self._toggle_comment_action)

        if self._format_action is not None and self._bind_shared_actions:
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

    def apply_text_case(self, transform: Callable[[str], str]) -> None:
        """Re-case the selection, or the word under the caret when nothing is selected."""

        if self.hasSelectedText():
            start_line, start_col, end_line, end_col = self.getSelection()
            text = self.selectedText()
        else:
            cursor_line, cursor_col = self.getCursorPosition()
            position = self.positionFromLineIndex(cursor_line, cursor_col)
            start = self.SendScintilla(self.SCI_WORDSTARTPOSITION, position, True)
            end = self.SendScintilla(self.SCI_WORDENDPOSITION, position, True)
            if start == end:
                return
            start_line, start_col = self.lineIndexFromPosition(start)
            end_line, end_col = self.lineIndexFromPosition(end)
            text = self.text()[start:end]

        replacement = transform_lines(text, transform)
        if replacement == text:
            return

        self.beginUndoAction()
        try:
            self.setSelection(start_line, start_col, end_line, end_col)
            self.replaceSelectedText(replacement)
        finally:
            self.endUndoAction()

    def format_selection_or_statement(self) -> None:
        text, start, end = self.text_to_run()
        if not text or start < 0 or end < 0:
            return

        cursor_line, cursor_column = self.getCursorPosition()
        visible_line = self.firstVisibleLine()
        horizontal_bar = self.horizontalScrollBar()
        horizontal = horizontal_bar.value() if horizontal_bar is not None else 0

        result = self._formatting_service.format_sql(text, dialect="duckdb")
        self.clear_diagnostics()

        if result.diagnostics:
            self.show_diagnostic(result.diagnostics[0], move_cursor=False)
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

    def show_diagnostic(self, diagnostic: SqlDiagnostic, *, move_cursor: bool = True) -> None:
        """Mark a diagnostic and, by default, move the user to its source position."""
        self.clear_diagnostics()
        line = max(diagnostic.start_line - 1, 0)
        line_count = max(self.lines(), 1)
        if line >= line_count:
            line = line_count - 1

        line_text = self.text(line).rstrip("\r\n")
        requested_column = max(diagnostic.start_column - 1, 0)
        cursor_column = min(requested_column, len(line_text))
        if not line_text or not line_text[:cursor_column].isascii():
            return

        marker_start = min(cursor_column, len(line_text) - 1)
        marker_end = marker_start + 1
        if diagnostic.end_line == line + 1 and diagnostic.end_column is not None:
            requested_end = max(diagnostic.end_column - 1, 0)
            marker_end = max(marker_end, min(requested_end, len(line_text)))

        try:
            self.fillIndicatorRange(
                line,
                marker_start,
                line,
                marker_end,
                self._diagnostic_indicator,
            )
        except Exception:  # noqa: BLE001
            return

        if move_cursor:
            self.setCursorPosition(line, cursor_column)
            self.ensureLineVisible(line)
            self.setFocus()

    def clear_diagnostics(self) -> None:
        """Remove all transient diagnostic indicators from the editor."""
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
        has_selection = self.hasSelectedText()
        cursor_line, cursor_column = self.getCursorPosition()
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

        self.beginUndoAction()
        try:
            self.selectAll(True)
            self.replaceSelectedText("".join(lines))
            if has_selection:
                end_line = line_end - 1
                end_column = len(self.text(end_line).rstrip("\r\n"))
                self.setSelection(line_start - 1, 0, end_line, end_column)
            else:
                self.setCursorPosition(cursor_line, cursor_column)
        finally:
            self.endUndoAction()
        self.setScrollWidth(1)

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

        self.set_text_undoable(replaced)
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
