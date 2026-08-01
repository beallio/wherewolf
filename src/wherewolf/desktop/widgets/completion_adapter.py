"""QScintilla SQL completion presentation adapter."""

from __future__ import annotations

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtGui import QColor, QPixmap

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CompletionContext, CompletionItem
from wherewolf.services.completion_context import detect_context
from wherewolf.services.completion_service import SqlCompletionService

COMPLETION_LIST_ID = 1

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
        items = self._service.complete(context)
        if not items:
            return

        cursor_ctx = detect_context(context.sql, context.cursor_offset)
        self._prefix = cursor_ctx.prefix
        self._active_items = {item.label: item for item in items}

        formatted = [f"{item.label}?{KIND_IMAGE_IDS.get(item.kind, 1)}" for item in items]
        self._editor.showUserList(COMPLETION_LIST_ID, formatted)

    def on_item_activated(self, list_id: int, text: str) -> None:
        if list_id != COMPLETION_LIST_ID:
            return

        item = self._active_items.get(text)
        insert_text = item.insert_text if item is not None else text

        line, col = self._editor.getCursorPosition()
        prefix_len = len(self._prefix)
        start_col = max(0, col - prefix_len)

        self._editor.beginUndoAction()
        try:
            self._editor.setSelection(line, start_col, line, col)
            self._editor.replaceSelectedText(insert_text)
        finally:
            self._editor.endUndoAction()


__all__ = ["COMPLETION_LIST_ID", "CompletionAdapter"]
