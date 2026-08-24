"""QScintilla SQL completion presentation adapter."""

from __future__ import annotations

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPixmap

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CompletionContext, CompletionItem
from wherewolf.services.completion_context import detect_context
from wherewolf.services.completion_service import SqlCompletionService

COMPLETION_LIST_ID = 1
_LIST_SEPARATOR = "\x1f"
_TYPE_SEPARATOR = "\x1e"

KIND_IMAGE_IDS: dict[CompletionKind, int] = {
    CompletionKind.TABLE: 1,
    CompletionKind.CTE: 2,
    CompletionKind.COLUMN: 3,
    CompletionKind.FUNCTION: 4,
    CompletionKind.KEYWORD: 5,
    CompletionKind.SNIPPET: 6,
}

KIND_COLORS: dict[CompletionKind, str] = {
    CompletionKind.TABLE: "#2b5c8f",
    CompletionKind.CTE: "#8f2b7f",
    CompletionKind.COLUMN: "#2b8f5c",
    CompletionKind.FUNCTION: "#8f5c2b",
    CompletionKind.KEYWORD: "#8f8f2b",
    CompletionKind.SNIPPET: "#5c5c5c",
}


class CompletionAdapter:
    """Adapts SqlCompletionService output to QScintilla autocompletion API."""

    def __init__(
        self,
        editor: QsciScintilla,
        completion_service: SqlCompletionService | None = None,
    ) -> None:
        self._editor = editor
        self._service = completion_service or SqlCompletionService()
        self._active_items: dict[str, CompletionItem] = {}
        self._prefix: str = ""
        self._request_generation = 0

        self._register_kind_images()
        self._editor.userListActivated.connect(self.on_item_activated)

    def _register_kind_images(self) -> None:
        for kind, type_id in KIND_IMAGE_IDS.items():
            pm = QPixmap(10, 10)
            pm.fill(QColor(KIND_COLORS.get(kind, "#888888")))
            try:
                self._editor.registerImage(type_id, pm)
            except Exception:  # noqa: BLE001, S110
                pass

    def request_completion(self, context: CompletionContext) -> None:
        self._request_generation += 1
        request_generation = self._request_generation
        items = self._service.complete(context)
        if not items:
            self._editor.SendScintilla(self._editor.SCI_AUTOCCANCEL, 0, b"")
            self._active_items = {}
            self._prefix = ""
            return

        cursor_ctx = detect_context(context.sql, context.cursor_offset)
        self._prefix = cursor_ctx.prefix
        self._active_items = {item.label: item for item in items}
        if self._editor.isListActive():
            self._editor.SendScintilla(self._editor.SCI_AUTOCCANCEL, 0, b"")

        def show_user_list() -> None:
            if request_generation != self._request_generation:
                return
            try:
                text = self._editor.text()
                line, column = self._editor.getCursorPosition()
                cursor_offset = self._editor.positionFromLineIndex(line, column)
                current_context = CompletionContext(
                    sql=text,
                    cursor_offset=cursor_offset,
                    dialect=context.dialect,
                    catalog=context.catalog,
                )
                current_items = self._service.complete(current_context)
                if not current_items:
                    self._active_items = {}
                    self._prefix = ""
                    self._editor.SendScintilla(self._editor.SCI_AUTOCCANCEL, 0, b"")
                    return
                current_cursor_ctx = detect_context(text, cursor_offset)
                self._prefix = current_cursor_ctx.prefix
                self._active_items = {item.label: item for item in current_items}
                formatted = [
                    f"{item.label}{_TYPE_SEPARATOR}{KIND_IMAGE_IDS.get(item.kind, 1)}"
                    for item in current_items
                ]
                self._editor.SendScintilla(
                    self._editor.SCI_AUTOCSETSEPARATOR, ord(_LIST_SEPARATOR), b""
                )
                self._editor.SendScintilla(
                    self._editor.SCI_AUTOCSETTYPESEPARATOR, ord(_TYPE_SEPARATOR), b""
                )
                self._editor.SendScintilla(
                    self._editor.SCI_USERLISTSHOW,
                    COMPLETION_LIST_ID,
                    _LIST_SEPARATOR.join(formatted).encode(),
                )
            except RuntimeError:
                # A delayed refresh may outlive its editor during tab/window shutdown.
                return

        # Let Scintilla finish processing the keystroke that changed the prefix before opening
        # the application-ranked list. Otherwise its normal prefix-popup teardown can close a
        # freshly shown user list in the same key event.
        QTimer.singleShot(150, show_user_list)

    def cancel(self) -> None:
        """Discard an open or delayed completion list without changing editor text."""

        self._request_generation += 1
        self._active_items = {}
        self._prefix = ""
        if self._editor.isListActive():
            self._editor.SendScintilla(self._editor.SCI_AUTOCCANCEL, 0, b"")

    def on_item_activated(self, list_id: int, text: str) -> None:
        if list_id != COMPLETION_LIST_ID:
            return

        item = self._active_items.get(text)
        if item is None:
            return

        line, col = self._editor.getCursorPosition()
        prefix_len = len(self._prefix)
        start_col = max(0, col - prefix_len)

        set_inserting = getattr(self._editor, "_set_completion_insertion_in_progress", None)
        if callable(set_inserting):
            set_inserting(True)
        self._editor.beginUndoAction()
        try:
            self._editor.setSelection(line, start_col, line, col)
            self._editor.replaceSelectedText(item.insert_text)
        finally:
            self._editor.endUndoAction()
            if callable(set_inserting):
                set_inserting(False)

        if self._editor.isListActive():
            self._editor.SendScintilla(self._editor.SCI_AUTOCCANCEL, 0, b"")
        self._active_items = {}
        if item.kind is CompletionKind.FUNCTION and item.detail:
            new_line, new_col = self._editor.getCursorPosition()
            position = self._editor.positionFromLineIndex(new_line, new_col)
            self._editor.SendScintilla(
                self._editor.SCI_CALLTIPSHOW,
                position,
                item.detail.encode(),
            )


__all__ = ["COMPLETION_LIST_ID", "CompletionAdapter"]
