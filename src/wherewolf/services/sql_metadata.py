"""Dialect SQL keyword and function metadata service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SqlFunctionInfo:
    name: str
    signature: str
    description: str | None = None


_COMMON_KEYWORDS: set[str] = {
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP BY",
    "HAVING",
    "ORDER BY",
    "LIMIT",
    "OFFSET",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "CROSS",
    "FULL",
    "ON",
    "AS",
    "WITH",
    "UNION",
    "ALL",
    "DISTINCT",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "AND",
    "OR",
    "NOT",
    "IN",
    "IS",
    "NULL",
    "LIKE",
    "ILIKE",
    "BETWEEN",
    "EXISTS",
    "CAST",
    "INSERT",
    "UPDATE",
    "DELETE",
    "CREATE",
    "DROP",
    "ALTER",
    "TABLE",
    "VIEW",
    "ASC",
    "DESC",
    "OVER",
    "PARTITION BY",
    "WINDOW",
    "FILTER",
}

_DUCKDB_KEYWORDS: set[str] = _COMMON_KEYWORDS | {
    "QUALIFY",
    "PIVOT",
    "UNPIVOT",
    "SUMMARIZE",
    "DESCRIBE",
    "EXCLUDE",
    "REPLACE",
    "SAMPLE",
    "USING",
    "POSITION",
}

_SPARK_KEYWORDS: set[str] = _COMMON_KEYWORDS | {
    "LATERAL VIEW",
    "LATERAL",
    "EXPLODE",
    "CLUSTER BY",
    "SORT BY",
    "DISTRIBUTE BY",
    "TABLESAMPLE",
}

_COMMON_FUNCTIONS: tuple[SqlFunctionInfo, ...] = (
    SqlFunctionInfo("COALESCE", "COALESCE(val1, val2, ...)"),
    SqlFunctionInfo("COUNT", "COUNT(expression)"),
    SqlFunctionInfo("SUM", "SUM(expression)"),
    SqlFunctionInfo("AVG", "AVG(expression)"),
    SqlFunctionInfo("MIN", "MIN(expression)"),
    SqlFunctionInfo("MAX", "MAX(expression)"),
    SqlFunctionInfo("CONCAT", "CONCAT(str1, str2, ...)"),
    SqlFunctionInfo("SUBSTRING", "SUBSTRING(string, start, length)"),
    SqlFunctionInfo("UPPER", "UPPER(string)"),
    SqlFunctionInfo("LOWER", "LOWER(string)"),
    SqlFunctionInfo("TRIM", "TRIM(string)"),
    SqlFunctionInfo("ROUND", "ROUND(number, decimals)"),
    SqlFunctionInfo("ABS", "ABS(number)"),
    SqlFunctionInfo("NOW", "NOW()"),
    SqlFunctionInfo("CURRENT_DATE", "CURRENT_DATE()"),
    SqlFunctionInfo("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()"),
    SqlFunctionInfo("DATE_TRUNC", "DATE_TRUNC(unit, timestamp)"),
    SqlFunctionInfo("NULLIF", "NULLIF(val1, val2)"),
    SqlFunctionInfo("NVL", "NVL(val, default_val)"),
    SqlFunctionInfo("ROW_NUMBER", "ROW_NUMBER() OVER (...)"),
    SqlFunctionInfo("RANK", "RANK() OVER (...)"),
    SqlFunctionInfo("DENSE_RANK", "DENSE_RANK() OVER (...)"),
)

_DUCKDB_FUNCTIONS: tuple[SqlFunctionInfo, ...] = _COMMON_FUNCTIONS + (
    SqlFunctionInfo("READ_PARQUET", "READ_PARQUET('path')"),
    SqlFunctionInfo("READ_CSV", "READ_CSV('path')"),
    SqlFunctionInfo("READ_JSON", "READ_JSON('path')"),
    SqlFunctionInfo("GENERATE_SERIES", "GENERATE_SERIES(start, stop, step)"),
    SqlFunctionInfo("ARRAY_EXTRACT", "ARRAY_EXTRACT(array, index)"),
    SqlFunctionInfo("STRFTIME", "STRFTIME(date, format)"),
)

_SPARK_FUNCTIONS: tuple[SqlFunctionInfo, ...] = _COMMON_FUNCTIONS + (
    SqlFunctionInfo("EXPLODE", "EXPLODE(expr)"),
    SqlFunctionInfo("COLLECT_LIST", "COLLECT_LIST(col)"),
    SqlFunctionInfo("COLLECT_SET", "COLLECT_SET(col)"),
    SqlFunctionInfo("GET_JSON_OBJECT", "GET_JSON_OBJECT(json, path)"),
    SqlFunctionInfo("FROM_JSON", "FROM_JSON(json, schema)"),
    SqlFunctionInfo("TO_JSON", "TO_JSON(expr)"),
)

_SUPPORTED_DIALECTS = {"duckdb", "spark"}


def _normalize_dialect(dialect: str) -> str:
    norm = dialect.strip().lower()
    if norm not in _SUPPORTED_DIALECTS:
        raise ValueError(f"Unknown or unsupported dialect: {dialect}")
    return norm


def get_dialect_keywords(dialect: str) -> set[str]:
    norm = _normalize_dialect(dialect)
    if norm == "duckdb":
        return set(_DUCKDB_KEYWORDS)
    if norm == "spark":
        return set(_SPARK_KEYWORDS)
    return set(_COMMON_KEYWORDS)


def get_dialect_functions(dialect: str) -> tuple[SqlFunctionInfo, ...]:
    norm = _normalize_dialect(dialect)
    if norm == "duckdb":
        return _DUCKDB_FUNCTIONS
    if norm == "spark":
        return _SPARK_FUNCTIONS
    return _COMMON_FUNCTIONS


def lookup_function_info(dialect: str, function_name: str) -> SqlFunctionInfo | None:
    funcs = get_dialect_functions(dialect)
    target = function_name.strip().upper()
    for fn in funcs:
        if fn.name.upper() == target:
            return fn
    return None


__all__ = [
    "SqlFunctionInfo",
    "get_dialect_functions",
    "get_dialect_keywords",
    "lookup_function_info",
]
