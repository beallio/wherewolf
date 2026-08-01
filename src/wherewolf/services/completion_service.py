"""SQL completion service."""

from __future__ import annotations

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CompletionContext, CompletionItem
from wherewolf.services.completion_context import CursorContextKind, detect_context


class SqlCompletionService:
    """Provides SQL code completion candidates given a completion context."""

    def complete(self, context: CompletionContext) -> tuple[CompletionItem, ...]:
        cursor_ctx = detect_context(context.sql, context.cursor_offset)
        if cursor_ctx.kind == CursorContextKind.SUPPRESSED:
            return ()

        items: list[CompletionItem] = []
        prefix = cursor_ctx.prefix.lower()

        if cursor_ctx.kind == CursorContextKind.TABLE_REF:
            for entry in context.catalog:
                alias = entry.alias
                if not prefix or alias.lower().startswith(prefix):
                    items.append(
                        CompletionItem(
                            label=alias,
                            insert_text=alias,
                            kind=CompletionKind.TABLE,
                            detail="table",
                            sort_key=(0, alias.lower()),
                        )
                    )

        return tuple(items)


__all__ = ["SqlCompletionService"]
