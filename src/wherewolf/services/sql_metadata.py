"""Dialect SQL keyword and function metadata service."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cache

import duckdb


class FunctionContext(StrEnum):
    """SQL positions in which a function may be completed."""

    EXPRESSION = "expression"
    TABLE = "table"


@dataclass(frozen=True, slots=True)
class SqlFunctionInfo:
    name: str
    signature: str
    description: str | None = None
    contexts: frozenset[FunctionContext] = frozenset({FunctionContext.EXPRESSION})


@dataclass(frozen=True, slots=True)
class _DuckDbFunctionCatalog:
    expression: tuple[SqlFunctionInfo, ...]
    table: tuple[SqlFunctionInfo, ...]
    all_functions: tuple[SqlFunctionInfo, ...]


MAX_SIGNATURE_DISPLAY_LENGTH = 96
_IDENTIFIER_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


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

_DUCKDB_EXPRESSION_FUNCTIONS: tuple[SqlFunctionInfo, ...] = _COMMON_FUNCTIONS + (
    SqlFunctionInfo("ARRAY_EXTRACT", "ARRAY_EXTRACT(array, index)"),
    SqlFunctionInfo("STRFTIME", "STRFTIME(date, format)"),
)

_DUCKDB_TABLE_FUNCTIONS: tuple[SqlFunctionInfo, ...] = (
    SqlFunctionInfo(
        "READ_PARQUET", "READ_PARQUET('path')", contexts=frozenset({FunctionContext.TABLE})
    ),
    SqlFunctionInfo("READ_CSV", "READ_CSV('path')", contexts=frozenset({FunctionContext.TABLE})),
    SqlFunctionInfo("READ_JSON", "READ_JSON('path')", contexts=frozenset({FunctionContext.TABLE})),
    SqlFunctionInfo(
        "GENERATE_SERIES",
        "GENERATE_SERIES(start, stop, step)",
        contexts=frozenset({FunctionContext.TABLE}),
    ),
)

# Kept as the immediate compatibility/failure fallback. The cached DuckDB loader upgrades it
# with the functions exposed by the locally installed engine.
_DUCKDB_FUNCTIONS: tuple[SqlFunctionInfo, ...] = (
    _DUCKDB_EXPRESSION_FUNCTIONS + _DUCKDB_TABLE_FUNCTIONS
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

_CURATED_DUCKDB_BY_NAME = {function.name.casefold(): function for function in _DUCKDB_FUNCTIONS}
_CURATED_DUCKDB_CATALOG = _DuckDbFunctionCatalog(
    expression=_DUCKDB_EXPRESSION_FUNCTIONS,
    table=_DUCKDB_TABLE_FUNCTIONS,
    all_functions=_DUCKDB_FUNCTIONS,
)


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
    """Return all locally known functions, preserving the historical public shape."""

    norm = _normalize_dialect(dialect)
    if norm == "duckdb":
        return _load_duckdb_catalog().all_functions
    if norm == "spark":
        return _SPARK_FUNCTIONS
    return _COMMON_FUNCTIONS


def get_dialect_expression_functions(dialect: str) -> tuple[SqlFunctionInfo, ...]:
    """Return functions valid in an expression position."""

    norm = _normalize_dialect(dialect)
    if norm == "duckdb":
        return _load_duckdb_catalog().expression
    if norm == "spark":
        return _SPARK_FUNCTIONS
    return _COMMON_FUNCTIONS


def get_dialect_table_functions(dialect: str) -> tuple[SqlFunctionInfo, ...]:
    """Return functions valid as a table reference."""

    norm = _normalize_dialect(dialect)
    if norm == "duckdb":
        return _load_duckdb_catalog().table
    if norm == "spark":
        return ()
    return ()


def lookup_function_info(dialect: str, function_name: str) -> SqlFunctionInfo | None:
    funcs = get_dialect_functions(dialect)
    target = function_name.strip().upper()
    for fn in funcs:
        if fn.name.upper() == target:
            return fn
    return None


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (tuple, list)):
        return tuple(str(item) for item in value if item is not None)
    return ()


def _render_dynamic_signature(name: str, rows: tuple[tuple[object, ...], ...]) -> str:
    signatures: set[str] = set()
    for row in rows:
        parameters = _string_tuple(row[3])
        varargs = str(row[5]) if len(row) > 5 and row[5] else ""
        rendered_parameters = list(parameters)
        if varargs:
            rendered_parameters.append("...")
        signatures.add(f"{name}({', '.join(rendered_parameters)})")

    ordered = sorted(
        signatures, key=lambda signature: (len(signature), signature.casefold(), signature)
    )
    primary = ordered[0] if ordered else f"{name}(...)"
    overload_suffix = "" if len(ordered) <= 1 else f" (+{len(ordered) - 1} overloads)"
    maximum_primary_length = MAX_SIGNATURE_DISPLAY_LENGTH - len(overload_suffix)
    if len(primary) > maximum_primary_length:
        primary = f"{primary[: maximum_primary_length - 4].rstrip(', ')}...)"
    return f"{primary}{overload_suffix}"


def _normalize_duckdb_rows(rows: tuple[tuple[object, ...], ...]) -> _DuckDbFunctionCatalog:
    """Normalize metadata rows without depending on DuckDB's overload row order."""

    grouped: dict[str, list[tuple[object, ...]]] = {}
    contexts: dict[str, set[FunctionContext]] = {}
    canonical_names: dict[str, str] = {}
    for row in rows:
        if len(row) < 6:
            continue
        raw_name, raw_type = row[0], row[1]
        if (
            not isinstance(raw_name, str)
            or not _IDENTIFIER_NAME.fullmatch(raw_name)
            or raw_name.casefold().startswith("pragma_")
        ):
            continue
        if not isinstance(raw_type, str):
            continue
        function_type = raw_type.casefold()
        if function_type not in {"scalar", "aggregate", "macro", "table", "table_macro"}:
            continue
        normalized_name = raw_name.casefold()
        grouped.setdefault(normalized_name, []).append(row)
        canonical_names.setdefault(normalized_name, raw_name.upper())
        target_context = (
            FunctionContext.TABLE
            if function_type in {"table", "table_macro"}
            else FunctionContext.EXPRESSION
        )
        contexts.setdefault(normalized_name, set()).add(target_context)

    functions: list[SqlFunctionInfo] = []
    for normalized_name in sorted(grouped, key=lambda name: (name, canonical_names[name])):
        name = canonical_names[normalized_name]
        function_contexts = frozenset(contexts[normalized_name])
        curated = _CURATED_DUCKDB_BY_NAME.get(normalized_name)
        if curated is not None:
            functions.append(replace(curated, contexts=function_contexts))
            continue
        function_rows = tuple(grouped[normalized_name])
        description = next(
            (
                row[2]
                for row in function_rows
                if len(row) > 2 and isinstance(row[2], str) and row[2].strip()
            ),
            None,
        )
        functions.append(
            SqlFunctionInfo(
                name=name,
                signature=_render_dynamic_signature(name, function_rows),
                description=description,
                contexts=function_contexts,
            )
        )

    dynamic_by_name = {function.name.casefold(): function for function in functions}
    for curated_name, curated_function in _CURATED_DUCKDB_BY_NAME.items():
        dynamic_by_name.setdefault(curated_name, curated_function)

    all_functions = tuple(
        sorted(
            dynamic_by_name.values(),
            key=lambda function: (function.name.casefold(), function.name),
        )
    )
    return _DuckDbFunctionCatalog(
        expression=tuple(
            function
            for function in all_functions
            if FunctionContext.EXPRESSION in function.contexts
        ),
        table=tuple(
            function for function in all_functions if FunctionContext.TABLE in function.contexts
        ),
        all_functions=all_functions,
    )


@cache
def _load_duckdb_catalog() -> _DuckDbFunctionCatalog:
    """Load the installed local DuckDB catalog once, falling back without surfacing errors."""

    connection: object | None = None
    try:
        connection = duckdb.connect(database=":memory:")
        rows = connection.execute(
            """
            SELECT function_name, function_type, description, parameters, parameter_types, varargs
            FROM duckdb_functions()
            WHERE function_type IN ('scalar', 'aggregate', 'macro', 'table', 'table_macro')
            """
        ).fetchall()
        return _normalize_duckdb_rows(tuple(tuple(row) for row in rows))
    except Exception:  # noqa: BLE001 - editor metadata must keep its curated fallback
        return _CURATED_DUCKDB_CATALOG
    finally:
        if connection is not None:
            connection.close()


__all__ = [
    "MAX_SIGNATURE_DISPLAY_LENGTH",
    "FunctionContext",
    "SqlFunctionInfo",
    "get_dialect_expression_functions",
    "get_dialect_functions",
    "get_dialect_keywords",
    "get_dialect_table_functions",
    "lookup_function_info",
]
