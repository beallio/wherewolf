"""Safe SQL construction and ordering analysis for captured-result pagination."""

from __future__ import annotations

import sqlglot

from wherewolf.services.statement_service import StatementService

_PAGE_ALIAS = "__wherewolf_page_7f3d6c91"


def build_page_sql(executable_sql: str) -> str:
    """Wrap exactly one captured statement in a parameterized page query."""
    statement_sql = _one_statement_sql(executable_sql)
    return f"SELECT * FROM ({statement_sql}) AS {_PAGE_ALIAS} LIMIT ? OFFSET ?"


def has_top_level_order_by(executable_sql: str) -> bool:
    """Return whether a parseable captured query has a final ``ORDER BY`` clause.

    This is deliberately syntactic: it cannot prove unique keys or rule out volatile
    expressions, so callers must still describe that limitation to users.
    """
    try:
        expression = sqlglot.parse_one(_one_statement_sql(executable_sql), read="duckdb")
    except Exception:  # noqa: BLE001 - analysis failure must retain the stability warning.
        return False
    return expression.args.get("order") is not None


def _one_statement_sql(executable_sql: str) -> str:
    statements = StatementService().split_statements(executable_sql)
    if len(statements) != 1:
        raise ValueError("Pagination requires exactly one executable statement")

    statement_sql = statements[0].text
    if statement_sql.endswith(";"):
        statement_sql = statement_sql[:-1].rstrip()
    if not statement_sql:
        raise ValueError("Pagination requires a non-empty executable statement")
    return statement_sql


__all__ = ["build_page_sql", "has_top_level_order_by"]
