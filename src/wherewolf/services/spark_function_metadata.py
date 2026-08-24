"""Lazy normalization and caching of the local Spark SQL function catalog."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from importlib import import_module
from threading import Lock
from typing import Any

from wherewolf.execution.spark_runtime import create_child_session
from wherewolf.services.sql_metadata import (
    _SPARK_FUNCTIONS,
    MAX_SIGNATURE_DISPLAY_LENGTH,
    FunctionContext,
    SqlFunctionInfo,
)

_IDENTIFIER_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SPECIAL_SYNTAX_NAMES = frozenset({"CASE", "WHEN", "THEN", "ELSE", "END"})
_KNOWN_GENERATORS = frozenset({"EXPLODE", "EXPLODE_OUTER", "INLINE", "INLINE_OUTER", "POSEXPLODE"})


@dataclass(frozen=True, slots=True)
class SparkFunctionMetadata:
    expression: tuple[SqlFunctionInfo, ...]
    table: tuple[SqlFunctionInfo, ...]
    all_functions: tuple[SqlFunctionInfo, ...]
    loaded: bool


_CURATED_BY_NAME = {function.name.casefold(): function for function in _SPARK_FUNCTIONS}
_CURATED_FUNCTIONS = tuple(
    replace(
        function,
        contexts=(
            frozenset({FunctionContext.EXPRESSION, FunctionContext.TABLE})
            if function.name == "EXPLODE"
            else function.contexts
        ),
    )
    for function in _SPARK_FUNCTIONS
)
_CURATED_METADATA = SparkFunctionMetadata(
    expression=_CURATED_FUNCTIONS,
    table=tuple(
        function for function in _CURATED_FUNCTIONS if FunctionContext.TABLE in function.contexts
    ),
    all_functions=_CURATED_FUNCTIONS,
    loaded=False,
)

_METADATA_LOCK = Lock()
_CACHED_METADATA: SparkFunctionMetadata | None = None


def _signature_from_description(name: str, description: str | None) -> str:
    if description:
        match = re.search(rf"\b{re.escape(name)}\s*\([^\n)]*\)", description, re.IGNORECASE)
        if match:
            signature = match.group(0)
            if len(signature) <= MAX_SIGNATURE_DISPLAY_LENGTH:
                return signature
            return f"{signature[: MAX_SIGNATURE_DISPLAY_LENGTH - 4].rstrip(', ')}...)"
    return f"{name}(...)"


def normalize_spark_functions(
    functions: Iterable[object], table_function_names: frozenset[str]
) -> SparkFunctionMetadata:
    """Normalize safe SQL names from Spark's already-listed local system catalog."""

    accepted: dict[str, str | None] = {}
    for function in functions:
        raw_name = getattr(function, "name", None)
        if not isinstance(raw_name, str) or not _IDENTIFIER_NAME.fullmatch(raw_name):
            continue
        name = raw_name.upper()
        if name in _SPECIAL_SYNTAX_NAMES:
            continue
        description = getattr(function, "description", None)
        accepted.setdefault(name, description if isinstance(description, str) else None)

    normalized_table_names = {name.upper() for name in table_function_names}
    normalized_table_names.intersection_update(accepted)
    functions_by_name: dict[str, SqlFunctionInfo] = {}
    for name, description in accepted.items():
        contexts = (
            frozenset({FunctionContext.EXPRESSION, FunctionContext.TABLE})
            if name in _KNOWN_GENERATORS
            else (
                frozenset({FunctionContext.TABLE})
                if name in normalized_table_names
                else frozenset({FunctionContext.EXPRESSION})
            )
        )
        curated = _CURATED_BY_NAME.get(name.casefold())
        if curated is not None:
            functions_by_name[name] = replace(curated, contexts=contexts)
        else:
            functions_by_name[name] = SqlFunctionInfo(
                name=name,
                signature=_signature_from_description(name, description),
                description=description,
                contexts=contexts,
            )

    for function in _CURATED_FUNCTIONS:
        functions_by_name.setdefault(function.name, function)

    all_functions = tuple(
        sorted(
            functions_by_name.values(),
            key=lambda function: (function.name.casefold(), function.name),
        )
    )
    return SparkFunctionMetadata(
        expression=tuple(
            function
            for function in all_functions
            if FunctionContext.EXPRESSION in function.contexts
        ),
        table=tuple(
            function for function in all_functions if FunctionContext.TABLE in function.contexts
        ),
        all_functions=all_functions,
        loaded=True,
    )


def _discover_table_function_names() -> frozenset[str]:
    """Read only Spark's public table-valued API surface after Spark has been started."""

    try:
        table_valued_function = import_module("pyspark.sql.tvf").TableValuedFunction
    except Exception:  # noqa: BLE001 - catalog normalization keeps its curated fallback
        return frozenset()
    return frozenset(
        name
        for name in dir(table_valued_function)
        if _IDENTIFIER_NAME.fullmatch(name) and not name.startswith("_")
    )


def current_spark_function_metadata() -> SparkFunctionMetadata:
    """Return the current immutable result without starting Spark or waiting for metadata."""

    return _CACHED_METADATA or _CURATED_METADATA


def load_spark_function_metadata(
    session_factory: Callable[[], Any] | None = None,
    table_function_names: frozenset[str] | None = None,
) -> SparkFunctionMetadata:
    """Blocking worker-only loader that caches one local child-session catalog result."""

    global _CACHED_METADATA
    with _METADATA_LOCK:
        if _CACHED_METADATA is not None:
            return _CACHED_METADATA
        try:
            child_session = (session_factory or create_child_session)()
            functions = child_session.catalog.listFunctions()
            discovered_table_names = (
                table_function_names
                if table_function_names is not None
                else _discover_table_function_names()
            )
            _CACHED_METADATA = normalize_spark_functions(functions, discovered_table_names)
        except Exception:  # noqa: BLE001 - the editor must retain a curated Spark fallback
            _CACHED_METADATA = _CURATED_METADATA
        return _CACHED_METADATA


def reset_spark_function_metadata_for_tests() -> None:
    """Clear only the metadata cache; the shared root Spark context remains owned by runtime."""

    global _CACHED_METADATA
    with _METADATA_LOCK:
        _CACHED_METADATA = None


__all__ = [
    "SparkFunctionMetadata",
    "current_spark_function_metadata",
    "load_spark_function_metadata",
    "normalize_spark_functions",
    "reset_spark_function_metadata_for_tests",
]
