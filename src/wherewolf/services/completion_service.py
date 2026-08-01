"""SQL completion service."""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import expressions as exp

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CatalogEntry, ColumnSchema, CompletionContext, CompletionItem
from wherewolf.services.completion_context import CursorContextKind, detect_context
from wherewolf.services.sql_metadata import (
    get_dialect_functions,
    get_dialect_keywords,
    lookup_function_info,
)


@dataclass(frozen=True, slots=True)
class _CteInfo:
    name: str
    columns: tuple[ColumnSchema, ...] | None


def _quote_identifier(name: str, dialect: str) -> str:
    if not name:
        return name
    keywords = get_dialect_keywords(dialect)
    needs_quotes = (
        bool(re.search(r"[^a-zA-Z0-9_]", name)) or name[0].isdigit() or name.upper() in keywords
    )
    if needs_quotes:
        return f'"{name}"'
    return name


class SqlCompletionService:
    """Provides SQL code completion candidates given a completion context."""

    def complete(self, context: CompletionContext) -> tuple[CompletionItem, ...]:
        cursor_ctx = detect_context(context.sql, context.cursor_offset)
        if cursor_ctx.kind == CursorContextKind.SUPPRESSED:
            return ()

        items: list[CompletionItem] = []
        prefix = cursor_ctx.prefix.lower()
        dialect = context.dialect

        ctes = self._find_ctes(context.sql, dialect, context.catalog)
        cte_map = {cte.name.lower(): cte for cte in ctes}

        if cursor_ctx.kind == CursorContextKind.TABLE_REF:
            added_names: set[str] = set()
            for cte in ctes:
                name_lower = cte.name.lower()
                if not prefix or name_lower.startswith(prefix):
                    insert_text = _quote_identifier(cte.name, dialect)
                    tier = 0 if prefix and name_lower == prefix else 1
                    items.append(
                        CompletionItem(
                            label=cte.name,
                            insert_text=insert_text,
                            kind=CompletionKind.CTE,
                            detail="CTE",
                            sort_key=(tier, name_lower),
                        )
                    )
                    added_names.add(name_lower)

            for entry in context.catalog:
                alias_lower = entry.alias.lower()
                if alias_lower in added_names:
                    continue
                if not prefix or alias_lower.startswith(prefix):
                    insert_text = _quote_identifier(entry.alias, dialect)
                    tier = 0 if prefix and alias_lower == prefix else 2
                    items.append(
                        CompletionItem(
                            label=entry.alias,
                            insert_text=insert_text,
                            kind=CompletionKind.TABLE,
                            detail="table",
                            sort_key=(tier, alias_lower),
                        )
                    )

        elif cursor_ctx.kind == CursorContextKind.QUALIFIED_COLUMN:
            qualifier = cursor_ctx.qualifier
            if qualifier:
                qual_lower = qualifier.lower()
                cols_to_add: tuple[ColumnSchema, ...] | None = None
                if qual_lower in cte_map:
                    cols_to_add = cte_map[qual_lower].columns
                else:
                    target_table = self._resolve_qualifier_to_table(
                        context.sql, context.cursor_offset, qualifier, dialect
                    )
                    if target_table:
                        entry = self._find_catalog_entry(context.catalog, target_table)
                        if entry is not None:
                            cols_to_add = entry.schema

                if cols_to_add:
                    for col in cols_to_add:
                        c_lower = col.name.lower()
                        if not prefix or c_lower.startswith(prefix):
                            insert_text = _quote_identifier(col.name, dialect)
                            items.append(
                                CompletionItem(
                                    label=col.name,
                                    insert_text=insert_text,
                                    kind=CompletionKind.COLUMN,
                                    detail=col.data_type,
                                    sort_key=(0, c_lower),
                                )
                            )

        elif cursor_ctx.kind == CursorContextKind.COLUMN_REF:
            # 1. In-scope CTEs (Tier 1)
            added_tables: set[str] = set()
            for cte in ctes:
                c_lower = cte.name.lower()
                if not prefix or c_lower.startswith(prefix):
                    tier = 0 if prefix and c_lower == prefix else 1
                    items.append(
                        CompletionItem(
                            label=cte.name,
                            insert_text=_quote_identifier(cte.name, dialect),
                            kind=CompletionKind.CTE,
                            detail="CTE",
                            sort_key=(tier, c_lower),
                        )
                    )
                    added_tables.add(c_lower)

            # 2. In-scope catalog tables (Tier 2)
            for entry in context.catalog:
                a_lower = entry.alias.lower()
                if a_lower not in added_tables and (not prefix or a_lower.startswith(prefix)):
                    tier = 0 if prefix and a_lower == prefix else 2
                    items.append(
                        CompletionItem(
                            label=entry.alias,
                            insert_text=_quote_identifier(entry.alias, dialect),
                            kind=CompletionKind.TABLE,
                            detail="table",
                            sort_key=(tier, a_lower),
                        )
                    )

            # 3. In-scope columns from referenced tables/CTEs (Tier 3)
            tables_in_query = self._find_tables_in_statement(context.sql, dialect)
            for tbl in tables_in_query:
                tbl_lower = tbl.lower()
                cols: tuple[ColumnSchema, ...] | None = None
                if tbl_lower in cte_map:
                    cols = cte_map[tbl_lower].columns
                else:
                    entry = self._find_catalog_entry(context.catalog, tbl)
                    if entry:
                        cols = entry.schema

                if cols:
                    for col in cols:
                        col_lower = col.name.lower()
                        if not prefix or col_lower.startswith(prefix):
                            tier = 0 if prefix and col_lower == prefix else 3
                            items.append(
                                CompletionItem(
                                    label=col.name,
                                    insert_text=_quote_identifier(col.name, dialect),
                                    kind=CompletionKind.COLUMN,
                                    detail=col.data_type,
                                    sort_key=(tier, col_lower),
                                )
                            )

            # 4. Dialect functions (Tier 4)
            funcs = get_dialect_functions(dialect)
            for fn in funcs:
                fn_lower = fn.name.lower()
                if not prefix or fn_lower.startswith(prefix):
                    tier = 0 if prefix and fn_lower == prefix else 4
                    items.append(
                        CompletionItem(
                            label=fn.name,
                            insert_text=f"{fn.name}(",
                            kind=CompletionKind.FUNCTION,
                            detail=fn.signature,
                            sort_key=(tier, fn_lower),
                        )
                    )

            # 5. Dialect keywords (Tier 5)
            keywords = get_dialect_keywords(dialect)
            for kw in keywords:
                kw_lower = kw.lower()
                if not prefix or kw_lower.startswith(prefix):
                    tier = 0 if prefix and kw_lower == prefix else 5
                    items.append(
                        CompletionItem(
                            label=kw,
                            insert_text=kw,
                            kind=CompletionKind.KEYWORD,
                            detail="keyword",
                            sort_key=(tier, kw_lower),
                        )
                    )

        # Stable sort by sort_key
        sorted_items = sorted(items, key=lambda x: (x.sort_key[0], x.sort_key[1], x.label))
        return tuple(sorted_items)

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

    def _find_tables_in_statement(self, sql: str, dialect: str) -> tuple[str, ...]:
        tables: set[str] = set()

        try:
            parsed = sqlglot.parse_one(sql, read=dialect)
            if parsed:
                for tbl in parsed.find_all(exp.Table):
                    if tbl.name:
                        tables.add(tbl.name)
                return tuple(tables)
        except Exception:  # noqa: BLE001, S110 - deliberate fallback to lexical scanner on parse error
            pass

        pattern = r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)"
        matches = re.finditer(pattern, sql, re.IGNORECASE)
        for match in matches:
            tables.add(match.group(1))

        return tuple(tables)

    @staticmethod
    def _find_catalog_entry(
        catalog: tuple[CatalogEntry, ...], table_name: str
    ) -> CatalogEntry | None:
        target = table_name.lower()
        for entry in catalog:
            if entry.alias.lower() == target:
                return entry
        return None

    def call_tip(self, context: CompletionContext) -> str | None:
        cursor_ctx = detect_context(context.sql, context.cursor_offset)
        if cursor_ctx.kind == CursorContextKind.SUPPRESSED:
            return None

        sql_before = context.sql[: context.cursor_offset]
        depth = 0
        idx = len(sql_before) - 1

        while idx >= 0:
            ch = sql_before[idx]
            if ch == ")":
                depth += 1
            elif ch == "(":
                if depth > 0:
                    depth -= 1
                else:
                    prefix_before_paren = sql_before[:idx].rstrip()
                    match = re.search(r"([a-zA-Z0-9_]+)$", prefix_before_paren)
                    if match:
                        fn_name = match.group(1)
                        info = lookup_function_info(context.dialect, fn_name)
                        if info is not None:
                            return info.signature
                    return None
            idx -= 1

        return None


__all__ = ["SqlCompletionService"]
