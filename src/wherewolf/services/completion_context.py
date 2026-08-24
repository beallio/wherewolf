"""Lexical SQL cursor context detector."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from wherewolf.services.statement_service import StatementService


class CursorContextKind(StrEnum):
    TABLE_REF = "table_ref"
    QUALIFIED_COLUMN = "qualified_column"
    COLUMN_REF = "column_ref"
    SUPPRESSED = "suppressed"


class CompletionClause(StrEnum):
    """Current statement clause used for context-sensitive completion."""

    UNKNOWN = "unknown"
    SELECT = "select"
    TABLE_REF = "table_ref"
    WHERE = "where"
    GROUP_BY = "group_by"
    HAVING = "having"
    QUALIFY = "qualify"
    ORDER_BY = "order_by"
    JOIN_ON = "join_on"


@dataclass(frozen=True, slots=True)
class CursorContext:
    kind: CursorContextKind
    prefix: str
    qualifier: str | None = None
    clause: CompletionClause = CompletionClause.UNKNOWN


def _detect_clause(before_prefix: str) -> CompletionClause:
    matches = list(
        re.finditer(
            r"\b(GROUP\s+BY|ORDER\s+BY|SELECT|FROM|JOIN|WHERE|HAVING|QUALIFY|ON|WITH)\b",
            before_prefix.upper(),
        )
    )
    if not matches:
        return CompletionClause.UNKNOWN

    clause_text = matches[-1].group(1)
    clauses = {
        "SELECT": CompletionClause.SELECT,
        "FROM": CompletionClause.TABLE_REF,
        "JOIN": CompletionClause.TABLE_REF,
        "WHERE": CompletionClause.WHERE,
        "GROUP BY": CompletionClause.GROUP_BY,
        "HAVING": CompletionClause.HAVING,
        "QUALIFY": CompletionClause.QUALIFY,
        "ORDER BY": CompletionClause.ORDER_BY,
        "ON": CompletionClause.JOIN_ON,
    }
    return clauses.get(clause_text, CompletionClause.UNKNOWN)


def detect_context(sql: str, cursor_offset: int) -> CursorContext:
    cursor_offset = max(cursor_offset, 0)
    cursor_offset = min(cursor_offset, len(sql))

    # 1. State scan up to cursor_offset to check string/comment suppression
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    escaped = False

    cursor = 0
    while cursor < cursor_offset:
        char = sql[cursor]
        nxt = sql[cursor + 1] if cursor + 1 < len(sql) else None

        if in_line_comment:
            if char in ("\r", "\n"):
                in_line_comment = False
            cursor += 1
            continue

        if in_block_comment:
            if char == "*" and nxt == "/":
                in_block_comment = False
                cursor += 2
                continue
            cursor += 1
            continue

        if in_single_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                if nxt == "'":
                    cursor += 1
                else:
                    in_single_quote = False
            cursor += 1
            continue

        if in_double_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                if nxt == '"':
                    cursor += 1
                else:
                    in_double_quote = False
            cursor += 1
            continue

        if char == "-" and nxt == "-":
            in_line_comment = True
            cursor += 2
            continue

        if char == "/" and nxt == "*":
            in_block_comment = True
            cursor += 2
            continue

        if char == "'":
            in_single_quote = True
            cursor += 1
            continue

        if char == '"':
            in_double_quote = True
            cursor += 1
            continue

        cursor += 1

    if in_single_quote or in_line_comment or in_block_comment:
        return CursorContext(kind=CursorContextKind.SUPPRESSED, prefix="")

    # 2. Extract statement text & relative cursor offset using StatementService
    stmt_service = StatementService()
    stmt_sel = stmt_service.find_statement(sql, cursor_offset)
    if stmt_sel.text is not None and stmt_sel.start_offset >= 0:
        stmt_sql = stmt_sel.text
        rel_offset = cursor_offset - stmt_sel.start_offset
        rel_offset = max(rel_offset, 0)
        rel_offset = min(rel_offset, len(stmt_sql))
    else:
        stmt_sql = sql[:cursor_offset]
        rel_offset = len(stmt_sql)

    # 3. Extract prefix & qualifier from text up to cursor_offset
    up_to_cursor = stmt_sql[:rel_offset]

    # Check for alias.prefix or alias.
    qual_match = re.search(r"([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]*)$", up_to_cursor)
    if qual_match:
        qualifier = qual_match.group(1)
        prefix = qual_match.group(2)
        return CursorContext(
            kind=CursorContextKind.QUALIFIED_COLUMN,
            prefix=prefix,
            qualifier=qualifier,
        )

    # Bare word prefix
    word_match = re.search(r"([a-zA-Z0-9_]+)$", up_to_cursor)
    prefix = word_match.group(1) if word_match else ""

    # Remove the prefix from up_to_cursor to find previous keywords
    before_prefix = up_to_cursor[: len(up_to_cursor) - len(prefix)].rstrip()

    clause = _detect_clause(before_prefix)
    if clause is CompletionClause.TABLE_REF:
        kind = CursorContextKind.TABLE_REF
    else:
        kind = CursorContextKind.COLUMN_REF

    return CursorContext(kind=kind, prefix=prefix, qualifier=None, clause=clause)


__all__ = ["CompletionClause", "CursorContext", "CursorContextKind", "detect_context"]
