"""SQL completion service."""

from __future__ import annotations

import re

import sqlglot
from sqlglot import expressions as exp

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CatalogEntry, CompletionContext, CompletionItem
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

        elif cursor_ctx.kind == CursorContextKind.QUALIFIED_COLUMN:
            qualifier = cursor_ctx.qualifier
            if qualifier:
                target_table = self._resolve_qualifier_to_table(
                    context.sql, context.cursor_offset, qualifier, context.dialect
                )
                if target_table:
                    entry = self._find_catalog_entry(context.catalog, target_table)
                    if entry is not None and entry.schema is not None:
                        for col in entry.schema:
                            if not prefix or col.name.lower().startswith(prefix):
                                items.append(
                                    CompletionItem(
                                        label=col.name,
                                        insert_text=col.name,
                                        kind=CompletionKind.COLUMN,
                                        detail=col.data_type,
                                        sort_key=(0, col.name.lower()),
                                    )
                                )

        return tuple(items)

    def _resolve_qualifier_to_table(
        self, sql: str, cursor_offset: int, qualifier: str, dialect: str
    ) -> str | None:
        qual_lower = qualifier.lower()

        # 1. Try SQLGlot AST
        try:
            parsed = sqlglot.parse_one(sql, read=dialect)
            if parsed:
                for table in parsed.find_all(exp.Table):
                    table_name = table.name
                    alias = table.alias
                    if alias and alias.lower() == qual_lower:
                        return table_name
                    if table_name and table_name.lower() == qual_lower:
                        return table_name
        except Exception:  # noqa: BLE001, S110 - deliberate fallback to lexical scanner on parse error
            pass

        # 2. Lexical fallback scan
        # Matches: FROM table [AS] alias  OR  JOIN table [AS] alias
        pattern = r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?"
        matches = re.finditer(pattern, sql, re.IGNORECASE)
        for match in matches:
            tbl = match.group(1)
            als = match.group(2)
            if als and als.lower() == qual_lower:
                return tbl
            if tbl and tbl.lower() == qual_lower:
                return tbl

        return None

    @staticmethod
    def _find_catalog_entry(
        catalog: tuple[CatalogEntry, ...], table_name: str
    ) -> CatalogEntry | None:
        target = table_name.lower()
        for entry in catalog:
            if entry.alias.lower() == target:
                return entry
        return None


__all__ = ["SqlCompletionService"]
