"""Full-query ORDER BY SQL generation."""

import re

from wherewolf.services.identifier_quoting import quote_identifier
from wherewolf.services.statement_service import StatementService

_CLAUSE_REQUIRES_WRAP_RE = re.compile(r"\b(ORDER\s+BY|LIMIT|OFFSET|WITH|UNION)\b", re.IGNORECASE)


def build_order_by_sql(sql: str, column_name: str, direction: str = "ASC") -> str:
    """Builds a full-query ORDER BY statement for the given SQL query and column.

    Stated Rules:
    1. The column identifier is quoted per `quote_identifier`.
    2. Direction is normalized to `ASC` or `DESC`.
    3. If the query has no existing `ORDER BY`, `LIMIT`, `OFFSET`, `WITH`, or `UNION` clause,
       append `ORDER BY <quoted_col> <direction>`.
    4. If the query already has `ORDER BY` or `LIMIT`/`OFFSET`/`WITH`/`UNION`, wrap the entire
       query as a subquery: `SELECT * FROM (<sql>) AS _subquery ORDER BY <quoted_col> <direction>`.

    Args:
        sql: The SQL query to order.
        column_name: The target column name.
        direction: Sort direction, 'ASC' or 'DESC'.

    Returns:
        The updated SQL query with ORDER BY applied.
    """
    cleaned_sql = sql.strip()
    if not cleaned_sql:
        return ""

    dir_upper = "DESC" if direction.upper() == "DESC" else "ASC"
    quoted_col = quote_identifier(column_name)

    # Use StatementService to ensure valid statement handling
    statement_service = StatementService()
    spans = statement_service.split_statements(cleaned_sql)
    if spans:
        target_sql = spans[-1].text.strip()
    else:
        target_sql = cleaned_sql

    if _CLAUSE_REQUIRES_WRAP_RE.search(target_sql):
        return f"SELECT * FROM ({target_sql}) AS _subquery ORDER BY {quoted_col} {dir_upper}"

    return f"{target_sql} ORDER BY {quoted_col} {dir_upper}"
