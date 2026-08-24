"""SQL completion service."""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import expressions as exp

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CatalogEntry, ColumnSchema, CompletionContext, CompletionItem
from wherewolf.services.completion_context import (
    CompletionClause,
    CursorContext,
    CursorContextKind,
    detect_context,
)
from wherewolf.services.completion_matching import match_identifier
from wherewolf.services.completion_symbols import AliasCategory, ExpressionAlias, collect_symbols
from wherewolf.services.sql_metadata import (
    get_dialect_expression_functions,
    get_dialect_keywords,
    get_dialect_table_functions,
    lookup_function_info,
)


@dataclass(frozen=True, slots=True)
class _CteInfo:
    name: str
    columns: tuple[ColumnSchema, ...] | None


@dataclass(frozen=True, slots=True)
class _CompletionCandidate:
    label: str
    insert_text: str
    kind: CompletionKind
    detail: str | None
    semantic_rank: int


_CURATED_FUNCTION_NAMES = frozenset(
    {
        "ABS",
        "AVG",
        "COALESCE",
        "CONCAT",
        "COUNT",
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
        "DATE_TRUNC",
        "LOWER",
        "MAX",
        "MIN",
        "NOW",
        "ROUND",
        "SUBSTRING",
        "SUM",
        "TRIM",
        "UPPER",
    }
)


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

        candidates: list[_CompletionCandidate] = []
        prefix = cursor_ctx.prefix
        dialect = context.dialect

        ctes = self._find_ctes(context.sql, dialect, context.catalog)
        cte_map = {cte.name.lower(): cte for cte in ctes}
        symbols = collect_symbols(context.sql, context.cursor_offset, dialect)
        table_aliases = {alias.name.casefold(): alias.relation for alias in symbols.table_aliases}

        if cursor_ctx.kind == CursorContextKind.TABLE_REF:
            added_names: set[str] = set()
            for cte in ctes:
                candidates.append(
                    _CompletionCandidate(
                        cte.name,
                        _quote_identifier(cte.name, dialect),
                        CompletionKind.CTE,
                        "CTE",
                        0,
                    )
                )
                added_names.add(cte.name.casefold())

            for entry in context.catalog:
                alias_lower = entry.alias.casefold()
                if alias_lower in added_names:
                    continue
                candidates.append(
                    _CompletionCandidate(
                        entry.alias,
                        _quote_identifier(entry.alias, dialect),
                        CompletionKind.TABLE,
                        "table",
                        2,
                    )
                )

            for function in get_dialect_table_functions(dialect):
                candidates.append(
                    _CompletionCandidate(
                        function.name,
                        f"{function.name}(",
                        CompletionKind.FUNCTION,
                        function.signature,
                        4,
                    )
                )

        elif cursor_ctx.kind == CursorContextKind.QUALIFIED_COLUMN:
            qualifier = cursor_ctx.qualifier
            if qualifier:
                qual_lower = qualifier.casefold()
                cols_to_add: tuple[ColumnSchema, ...] | None = None
                if qual_lower in cte_map:
                    cols_to_add = cte_map[qual_lower].columns
                else:
                    target_table = table_aliases.get(
                        qual_lower
                    ) or self._resolve_qualifier_to_table(
                        context.sql, context.cursor_offset, qualifier, dialect
                    )
                    if target_table:
                        entry = self._find_catalog_entry(context.catalog, target_table)
                        if entry is not None:
                            cols_to_add = entry.schema

                if cols_to_add:
                    for col in cols_to_add:
                        candidates.append(
                            _CompletionCandidate(
                                col.name,
                                _quote_identifier(col.name, dialect),
                                CompletionKind.COLUMN,
                                col.data_type,
                                0,
                            )
                        )

        elif cursor_ctx.kind == CursorContextKind.COLUMN_REF:
            added_tables: set[str] = set()
            for cte in ctes:
                candidates.append(
                    _CompletionCandidate(
                        cte.name,
                        _quote_identifier(cte.name, dialect),
                        CompletionKind.CTE,
                        "CTE",
                        0,
                    )
                )
                added_tables.add(cte.name.casefold())

            for alias in symbols.table_aliases:
                candidates.append(
                    _CompletionCandidate(
                        alias.name,
                        _quote_identifier(alias.name, dialect),
                        CompletionKind.TABLE,
                        f"alias for {alias.relation}",
                        1,
                    )
                )

            for entry in context.catalog:
                a_lower = entry.alias.casefold()
                if a_lower not in added_tables:
                    candidates.append(
                        _CompletionCandidate(
                            entry.alias,
                            _quote_identifier(entry.alias, dialect),
                            CompletionKind.TABLE,
                            "table",
                            2,
                        )
                    )

            visible_relations = list(self._find_tables_in_statement(context.sql, dialect))
            visible_relations.extend(alias.relation for alias in symbols.table_aliases)
            for tbl in dict.fromkeys(visible_relations):
                tbl_lower = tbl.casefold()
                cols: tuple[ColumnSchema, ...] | None = None
                if tbl_lower in cte_map:
                    cols = cte_map[tbl_lower].columns
                else:
                    entry = self._find_catalog_entry(context.catalog, tbl)
                    if entry:
                        cols = entry.schema

                if cols:
                    for col in cols:
                        candidates.append(
                            _CompletionCandidate(
                                col.name,
                                _quote_identifier(col.name, dialect),
                                CompletionKind.COLUMN,
                                col.data_type,
                                3,
                            )
                        )

            for alias in self._visible_expression_aliases(
                symbols.expression_aliases, cursor_ctx, dialect
            ):
                candidates.append(
                    _CompletionCandidate(
                        alias.name,
                        _quote_identifier(alias.name, dialect),
                        CompletionKind.COLUMN,
                        "column alias",
                        3,
                    )
                )

            for function in get_dialect_expression_functions(dialect):
                candidates.append(
                    _CompletionCandidate(
                        function.name,
                        f"{function.name}(",
                        CompletionKind.FUNCTION,
                        function.signature,
                        4,
                    )
                )

            for keyword in get_dialect_keywords(dialect):
                candidates.append(
                    _CompletionCandidate(
                        keyword,
                        keyword,
                        CompletionKind.KEYWORD,
                        "keyword",
                        5,
                    )
                )

        return self._rank_candidates(candidates, prefix)

    @staticmethod
    def _visible_expression_aliases(
        aliases: tuple[ExpressionAlias, ...], cursor_ctx: CursorContext, dialect: str
    ) -> tuple[ExpressionAlias, ...]:
        """Apply dialect clause visibility without exposing select-list lateral aliases."""

        clause = cursor_ctx.clause
        if clause is CompletionClause.ORDER_BY:
            return aliases
        if dialect.casefold() != "duckdb":
            return ()
        if clause in {CompletionClause.WHERE, CompletionClause.GROUP_BY}:
            return tuple(
                alias for alias in aliases if alias.category is AliasCategory.NON_AGGREGATE
            )
        if clause is CompletionClause.HAVING:
            return tuple(alias for alias in aliases if alias.category is AliasCategory.AGGREGATE)
        if clause is CompletionClause.QUALIFY:
            return tuple(alias for alias in aliases if alias.category is AliasCategory.WINDOW)
        return ()

    @staticmethod
    def _rank_candidates(
        candidates: list[_CompletionCandidate], prefix: str
    ) -> tuple[CompletionItem, ...]:
        ranked: list[tuple[int, str, _CompletionCandidate]] = []
        for candidate in candidates:
            match = match_identifier(prefix, candidate.label)
            if match is None:
                continue
            if prefix:
                rank = int(match.quality) * 10 + candidate.semantic_rank
            elif candidate.kind is CompletionKind.KEYWORD:
                rank = 4
            elif candidate.kind is CompletionKind.FUNCTION:
                rank = 5 if candidate.label.upper() in _CURATED_FUNCTION_NAMES else 6
            else:
                rank = candidate.semantic_rank
            ranked.append((rank, candidate.label.casefold(), candidate))

        deduplicated: dict[str, tuple[int, str, _CompletionCandidate]] = {}
        for ranked_candidate in sorted(
            ranked, key=lambda value: (value[0], value[1], value[2].label)
        ):
            deduplicated.setdefault(ranked_candidate[1], ranked_candidate)

        return tuple(
            CompletionItem(
                label=candidate.label,
                insert_text=candidate.insert_text,
                kind=candidate.kind,
                detail=candidate.detail,
                sort_key=(rank, normalized_label),
            )
            for rank, normalized_label, candidate in list(deduplicated.values())[:100]
        )

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
