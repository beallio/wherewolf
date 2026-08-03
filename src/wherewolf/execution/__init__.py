from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .duckdb_engine import DuckDBEngine
    from .models import QueryResult
    from .spark_engine import SparkEngine


def __getattr__(name: str):
    if name == "DuckDBEngine":
        from .duckdb_engine import DuckDBEngine

        return DuckDBEngine

    if name == "SparkEngine":
        from .spark_engine import SparkEngine

        return SparkEngine

    if name == "QueryResult":
        from .models import QueryResult

        return QueryResult

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return [
        "DuckDBEngine",
        "QueryResult",
        "SparkEngine",
    ]


__all__ = ["DuckDBEngine", "QueryResult", "SparkEngine"]
