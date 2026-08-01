"""SQL completion service."""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import expressions as exp

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CatalogEntry, ColumnSchema, CompletionContext, CompletionItem
from wherewolf.services.completion_context import CursorContextKind, detect_context


@dataclass(frozen=True, slots=True)
class _CteInfo:
    name: str
    columns: tuple[ColumnSchema, ...] | None


class SqlCompletionService:
    """Provides SQL code completion candidates given a completion context."""

    def complete(self, context: CompletionContext) -> tuple[CompletionItem, ...]:
        cursor_ctx = detect_context(context.sql, context.cursor_offset)
        if cursor_ctx.kind == CursorContextKind.SUPPRESSED:
            return ()

        items: list[CompletionItem] = []
        prefix = cursor_ctx.prefix.lower()

        ctes = self._find_ctes(context.sql, context.dialect, context.catalog)
        cte_map = {cte.name.lower(): cte for cte in ctes}

        if cursor_ctx.kind == CursorContextKind.TABLE_REF:
            # Add CTEs first (shadowing catalog aliases if same name)
            added_names: set[str] = set()
            for cte in ctes:
                name_lower = cte.name.lower()
                if not prefix or name_lower.startswith(prefix):
                    items.append(
                        CompletionItem(
                            label=cte.name,
                            insert_text=cte.name,
                            kind=CompletionKind.CTE,
                            detail="CTE",
                            sort_key=(0, name_lower),
                        )
                    )
                    added_names.add(name_lower)

            # Add catalog tables not shadowed by CTEs
            for entry in context.catalog:
                alias_lower = entry.alias.lower()
                if alias_lower in added_names:
                    continue
                if not prefix or alias_lower.startswith(prefix):
                    items.append(
                        CompletionItem(
                            label=entry.alias,
                            insert_text=entry.alias,
                            kind=CompletionKind.TABLE,
                            detail="table",
                            sort_key=(0, alias_lower),
                        )
                    )

        elif cursor_ctx.kind == CursorContextKind.QUALIFIED_COLUMN:
            qualifier = cursor_ctx.qualifier
            if qualifier:
                qual_lower = qualifier.lower()
                # Check if qualifier is a CTE
                if qual_lower in cte_map:
                    cte_info = cte_map[qual_lower]
                    if cte_info.columns is not None:
                        for col in cte_info.columns:
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
                else:
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

    def _find_ctes(
        self, sql: str, dialect: str, catalog: tuple[CatalogEntry, ...]
    ) -> tuple[_CteInfo, ...]:
        ctes: list[_CteInfo] = []

        candidate_sqls = [sql, re.sub(r"\.[a-zA-Z0-9_]*$", "", sql)]
        for cand in candidate_sqls:
            try:
                parsed = sqlglot.parse_one(cand, read=dialect)
                if parsed:
                    for cte in parsed.find_all(exp.CTE):
                        cte_name = cte.alias
                        if not cte_name:
                            continue
                        columns = self._derive_cte_columns(cte, catalog)
                        ctes.append(_CteInfo(name=cte_name, columns=columns))
                    if ctes:
                        return tuple(ctes)
            except Exception:  # noqa: BLE001, S110 - deliberate fallback to lexical scanner on parse error
                pass

        cte_star_pattern = (
            r"\b([a-zA-Z0-9_]+)\s+AS\s*\(\s*SELECT\s+\*\s+FROM\s+([a-zA-Z0-9_]+)\s*\)"
        )
        star_matches = re.finditer(cte_star_pattern, sql, re.IGNORECASE)
        found_lexical: dict[str, tuple[ColumnSchema, ...] | None] = {}
        for match in star_matches:
            cte_name = match.group(1)
            src_table = match.group(2)
            entry = self._find_catalog_entry(catalog, src_table)
            found_lexical[cte_name] = entry.schema if (entry and entry.schema) else None

        fallback_matches = re.finditer(r"\b([a-zA-Z0-9_]+)\s+AS\s*\(", sql, re.IGNORECASE)
        for match in fallback_matches:
            cte_name = match.group(1)
            if (
                cte_name.upper() not in {"SELECT", "WITH", "FROM", "JOIN", "WHERE"}
                and cte_name not in found_lexical
            ):
                found_lexical[cte_name] = None

        for name, cols in found_lexical.items():
            ctes.append(_CteInfo(name=name, columns=cols))

        return tuple(ctes)

    def _derive_cte_columns(
        self, cte: exp.CTE, catalog: tuple[CatalogEntry, ...]
    ) -> tuple[ColumnSchema, ...] | None:
        inner = cte.this
        if not isinstance(inner, exp.Select):
            return None

        select_expressions = inner.expressions
        table = inner.find(exp.Table)
        if table and len(select_expressions) == 1 and isinstance(select_expressions[0], exp.Star):
            entry = self._find_catalog_entry(catalog, table.name)
            if entry and entry.schema:
                return entry.schema

        cols: list[ColumnSchema] = []
        for expr in select_expressions:
            if isinstance(expr, exp.Alias):
                cols.append(ColumnSchema(name=expr.alias, data_type="UNKNOWN"))
            elif isinstance(expr, exp.Column):
                cols.append(ColumnSchema(name=expr.name, data_type="UNKNOWN"))

        return tuple(cols) if cols else None

    def _resolve_qualifier_to_table(
        self, sql: str, cursor_offset: int, qualifier: str, dialect: str
    ) -> str | None:
        qual_lower = qualifier.lower()

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
