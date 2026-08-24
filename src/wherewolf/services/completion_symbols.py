"""Statement-scoped SQL aliases for completion without catalog or UI dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

import sqlglot
from sqlglot import expressions as exp

from wherewolf.services.statement_service import StatementService


class AliasCategory(StrEnum):
    """DuckDB visibility category for a SELECT-expression alias."""

    NON_AGGREGATE = "non_aggregate"
    AGGREGATE = "aggregate"
    WINDOW = "window"


@dataclass(frozen=True, slots=True)
class TableAlias:
    name: str
    relation: str


@dataclass(frozen=True, slots=True)
class ExpressionAlias:
    name: str
    category: AliasCategory


@dataclass(frozen=True, slots=True)
class CompletionSymbols:
    table_aliases: tuple[TableAlias, ...] = ()
    expression_aliases: tuple[ExpressionAlias, ...] = ()


@dataclass(frozen=True, slots=True)
class _SelectScope:
    start: int
    container_open: int | None
    depth: int


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_ALIAS_STOP_WORDS = {
    "WHERE",
    "GROUP",
    "HAVING",
    "QUALIFY",
    "ORDER",
    "JOIN",
    "ON",
    "LIMIT",
    "OFFSET",
    "UNION",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "CROSS",
    "FULL",
}


def _scan_select_scopes(
    sql: str, cursor_offset: int
) -> tuple[tuple[_SelectScope, ...], tuple[int, ...]]:
    scopes: list[_SelectScope] = []
    stack: list[int] = []
    cursor_stack: tuple[int, ...] = ()
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    index = 0

    while index < len(sql):
        if index == cursor_offset:
            cursor_stack = tuple(stack)

        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue
        if in_single_quote:
            if char == "'":
                if next_char == "'":
                    index += 2
                    continue
                in_single_quote = False
            index += 1
            continue
        if in_double_quote:
            if char == '"':
                if next_char == '"':
                    index += 2
                    continue
                in_double_quote = False
            index += 1
            continue
        if char == "-" and next_char == "-":
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        if char == "'":
            in_single_quote = True
            index += 1
            continue
        if char == '"':
            in_double_quote = True
            index += 1
            continue
        if char == "(":
            stack.append(index)
            index += 1
            continue
        if char == ")":
            if stack:
                stack.pop()
            index += 1
            continue

        if (
            sql[index : index + 6].upper() == "SELECT"
            and (index == 0 or not (sql[index - 1].isalnum() or sql[index - 1] == "_"))
            and (index + 6 == len(sql) or not (sql[index + 6].isalnum() or sql[index + 6] == "_"))
        ):
            scopes.append(
                _SelectScope(
                    start=index,
                    container_open=stack[-1] if stack else None,
                    depth=len(stack),
                )
            )
            index += 6
            continue
        index += 1

    if cursor_offset >= len(sql):
        cursor_stack = tuple(stack)
    return tuple(scopes), cursor_stack


def _scope_for_cursor(sql: str, cursor_offset: int) -> _SelectScope | None:
    scopes, cursor_stack = _scan_select_scopes(sql, cursor_offset)
    active = [
        scope
        for scope in scopes
        if scope.start <= cursor_offset
        and (scope.container_open is None or scope.container_open in cursor_stack)
    ]
    if not active:
        return None
    return max(active, key=lambda scope: (scope.depth, scope.start))


def _mask_other_scopes(sql: str, scope: _SelectScope) -> str:
    """Retain text directly in *scope* while masking nested scopes and quoted text."""

    output = list(sql)
    stack: list[int] = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    index = 0

    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        direct_scope = (stack[-1] if stack else None) == scope.container_open
        if (
            not direct_scope
            or in_single_quote
            or in_double_quote
            or in_line_comment
            or in_block_comment
        ):
            output[index] = " "

        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                output[index + 1] = " "
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue
        if in_single_quote:
            if char == "'":
                if next_char == "'":
                    output[index + 1] = " "
                    index += 2
                    continue
                in_single_quote = False
            index += 1
            continue
        if in_double_quote:
            if char == '"':
                if next_char == '"':
                    output[index + 1] = " "
                    index += 2
                    continue
                in_double_quote = False
            index += 1
            continue
        if char == "-" and next_char == "-":
            output[index] = output[index + 1] = " "
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            output[index] = output[index + 1] = " "
            in_block_comment = True
            index += 2
            continue
        if char == "'":
            output[index] = " "
            in_single_quote = True
            index += 1
            continue
        if char == '"':
            output[index] = " "
            in_double_quote = True
            index += 1
            continue
        if char == "(":
            stack.append(index)
        elif char == ")" and stack:
            stack.pop()
        index += 1
    return "".join(output)


def _alias_category(expression: exp.Expression) -> AliasCategory:
    if expression.find(exp.Window) is not None:
        return AliasCategory.WINDOW
    if expression.find(exp.AggFunc) is not None:
        return AliasCategory.AGGREGATE
    return AliasCategory.NON_AGGREGATE


def _table_aliases_from_select(select: exp.Select) -> tuple[TableAlias, ...]:
    tables: list[exp.Table] = []
    from_clause = select.args.get("from_")
    if isinstance(from_clause, exp.From) and isinstance(from_clause.this, exp.Table):
        tables.append(from_clause.this)
    for join in select.args.get("joins") or ():
        if isinstance(join, exp.Join) and isinstance(join.this, exp.Table):
            tables.append(join.this)

    aliases: list[TableAlias] = []
    for table in tables:
        relation = table.name
        alias = table.alias
        if relation and alias and alias.casefold() != relation.casefold():
            aliases.append(TableAlias(name=alias, relation=relation))
    return tuple(aliases)


def _expression_aliases_from_select(
    select: exp.Select, cursor_offset: int
) -> tuple[ExpressionAlias, ...]:
    aliases: list[ExpressionAlias] = []
    for expression in select.expressions:
        if not isinstance(expression, exp.Alias) or not expression.alias:
            continue
        alias_expression = expression.args.get("alias")
        alias_start = alias_expression.meta.get("start") if alias_expression is not None else None
        if isinstance(alias_start, int) and alias_start >= cursor_offset:
            continue
        aliases.append(ExpressionAlias(expression.alias, _alias_category(expression.this)))
    return tuple(aliases)


def _lexical_table_aliases(masked_sql: str) -> tuple[TableAlias, ...]:
    aliases: list[TableAlias] = []
    pattern = re.compile(
        rf"\b(?:FROM|JOIN)\s+({_IDENTIFIER})(?:\s+(?:AS\s+)?({_IDENTIFIER}))?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(masked_sql):
        relation, alias = match.groups()
        if alias and alias.upper() not in _ALIAS_STOP_WORDS:
            aliases.append(TableAlias(name=alias, relation=relation))
    return tuple(aliases)


def _lexical_expression_aliases(masked_sql: str, cursor_offset: int) -> tuple[ExpressionAlias, ...]:
    aliases: list[ExpressionAlias] = []
    for match in re.finditer(rf"\bAS\s+({_IDENTIFIER})\b", masked_sql, re.IGNORECASE):
        if match.start(1) >= cursor_offset:
            continue
        expression_text = masked_sql[max(0, match.start() - 120) : match.start()]
        aliases.append(
            ExpressionAlias(
                name=match.group(1),
                category=_lexical_alias_category(expression_text),
            )
        )
    for match in re.finditer(rf"\b({_IDENTIFIER})\s*:", masked_sql):
        if match.start(1) >= cursor_offset:
            continue
        expression_text = masked_sql[match.end() : match.end() + 120]
        aliases.append(
            ExpressionAlias(
                name=match.group(1),
                category=_lexical_alias_category(expression_text),
            )
        )
    return tuple(aliases)


def _lexical_alias_category(expression_text: str) -> AliasCategory:
    if re.search(r"\bOVER\s*\(", expression_text, re.IGNORECASE):
        return AliasCategory.WINDOW
    if re.search(r"\b(?:AVG|COUNT|MAX|MIN|SUM)\s*\(", expression_text, re.IGNORECASE):
        return AliasCategory.AGGREGATE
    return AliasCategory.NON_AGGREGATE


def collect_symbols(sql: str, cursor_offset: int, dialect: str) -> CompletionSymbols:
    """Collect aliases from the cursor's statement and innermost visible SELECT scope."""

    statement_service = StatementService()
    selection = statement_service.find_statement(sql, cursor_offset)
    if selection.text is None and cursor_offset == len(sql) and cursor_offset:
        selection = statement_service.find_statement(sql, cursor_offset - 1)
    if selection.text is None:
        return CompletionSymbols()

    statement_sql = selection.text
    relative_cursor = max(0, min(cursor_offset - selection.start_offset, len(statement_sql)))
    scope = _scope_for_cursor(statement_sql, relative_cursor)
    if scope is None:
        return CompletionSymbols()

    try:
        parsed = sqlglot.parse_one(statement_sql, read=dialect)
        selects = tuple(parsed.find_all(exp.Select)) if parsed is not None else ()
        scopes, _ = _scan_select_scopes(statement_sql, relative_cursor)
        select_index = scopes.index(scope)
        if select_index < len(selects):
            select = selects[select_index]
            return CompletionSymbols(
                table_aliases=_table_aliases_from_select(select),
                expression_aliases=_expression_aliases_from_select(select, relative_cursor),
            )
    except Exception:  # noqa: BLE001, S110 - incomplete SQL deliberately uses lexical fallback
        pass

    masked_sql = _mask_other_scopes(statement_sql, scope)
    return CompletionSymbols(
        table_aliases=_lexical_table_aliases(masked_sql),
        expression_aliases=_lexical_expression_aliases(masked_sql, relative_cursor),
    )


__all__ = [
    "AliasCategory",
    "CompletionSymbols",
    "ExpressionAlias",
    "TableAlias",
    "collect_symbols",
]
