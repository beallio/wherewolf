from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import util
from uuid import UUID

import polars as pl

from wherewolf.domain import (
    CatalogEntry,
    ColumnSchema,
    EngineKind,
    EngineUnavailableError,
    ExecutionRequest,
    ExecutionStatus,
    QueryResult,
    SchemaResult,
)
from wherewolf.execution.base import CancellationHandle, ExecutionEngine


@dataclass(frozen=True, slots=True)
class EngineDescriptor:
    kind: EngineKind
    display_name: str
    available: bool
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class _CancellationHandle:
    request_id: UUID
    _cancel: Callable[[], None]

    def cancel(self) -> bool:
        self._cancel()
        return True


class _BaseAdapter:
    def __init__(
        self,
        request_id: UUID,
        execute_fn: Callable[[ExecutionRequest], QueryResult],
        schema_fn: Callable[[CatalogEntry], SchemaResult],
        close_fn: Callable[[], None],
    ):
        self._request_id = request_id
        self._execute_fn = execute_fn
        self._schema_fn = schema_fn
        self._close_fn = close_fn

    def cancellation_handle(self) -> CancellationHandle:
        return _CancellationHandle(request_id=self._request_id, _cancel=self._cancel)

    @property
    def _cancel(self) -> Callable[[], None]:
        raise NotImplementedError

    def execute_preview(self, request: ExecutionRequest) -> QueryResult:
        return self._execute_fn(request)

    def inspect_schema(self, entry: CatalogEntry) -> SchemaResult:
        return self._schema_fn(entry)

    def close(self) -> None:
        self._close_fn()


class _DuckDBAdapter(_BaseAdapter):
    def __init__(self, request_id: UUID):
        from .duckdb_engine import DuckDBEngine

        self._engine = DuckDBEngine()

        def execute_fn(request: ExecutionRequest) -> QueryResult:
            catalog = {binding.alias: str(binding.path) for binding in request.catalog}
            legacy_result = self._engine.execute(
                request.executable_sql,
                catalog=catalog,
                limit=request.preview_limit,
            )

            if not legacy_result.success:
                return QueryResult(
                    request_id=request.request_id,
                    status=ExecutionStatus.FAILED,
                    frame=None,
                    execution_seconds=legacy_result.execution_time,
                    preview_row_count=legacy_result.row_count,
                    total_row_count=legacy_result.row_count,
                    truncated=legacy_result.is_truncated,
                    completed_at=datetime.now(UTC),
                    error_type="execution_failed",
                    error_message=legacy_result.error_message,
                )

            return QueryResult(
                request_id=request.request_id,
                status=ExecutionStatus.SUCCEEDED,
                frame=legacy_result.df,
                execution_seconds=legacy_result.execution_time,
                preview_row_count=legacy_result.row_count,
                total_row_count=legacy_result.row_count,
                truncated=legacy_result.is_truncated,
                completed_at=datetime.now(UTC),
            )

        def schema_fn(entry: CatalogEntry) -> SchemaResult:
            schema = self._engine.get_schema(str(entry.path))
            return SchemaResult(
                entry_id=entry.id,
                columns=_frame_to_columns(schema),
            )

        super().__init__(
            request_id=request_id,
            execute_fn=execute_fn,
            schema_fn=schema_fn,
            close_fn=self._engine.interrupt,
        )

    @property
    def _cancel(self) -> Callable[[], None]:
        return self._engine.interrupt


class _SparkAdapter(_BaseAdapter):
    def __init__(self, request_id: UUID):
        from .spark_engine import SparkEngine

        self._engine = SparkEngine()

        def execute_fn(request: ExecutionRequest) -> QueryResult:
            catalog = {binding.alias: str(binding.path) for binding in request.catalog}
            legacy_result = self._engine.execute(
                request.executable_sql,
                catalog=catalog,
                limit=request.preview_limit,
            )

            if not legacy_result.success:
                return QueryResult(
                    request_id=request.request_id,
                    status=ExecutionStatus.FAILED,
                    frame=None,
                    execution_seconds=legacy_result.execution_time,
                    preview_row_count=legacy_result.row_count,
                    total_row_count=legacy_result.row_count,
                    truncated=legacy_result.is_truncated,
                    completed_at=datetime.now(UTC),
                    error_type="execution_failed",
                    error_message=legacy_result.error_message,
                )

            return QueryResult(
                request_id=request.request_id,
                status=ExecutionStatus.SUCCEEDED,
                frame=legacy_result.df,
                execution_seconds=legacy_result.execution_time,
                preview_row_count=legacy_result.row_count,
                total_row_count=legacy_result.row_count,
                truncated=legacy_result.is_truncated,
                completed_at=datetime.now(UTC),
            )

        def schema_fn(entry: CatalogEntry) -> SchemaResult:
            schema = self._engine.get_schema(str(entry.path))
            return SchemaResult(entry_id=entry.id, columns=_frame_to_columns(schema))

        super().__init__(
            request_id=request_id,
            execute_fn=execute_fn,
            schema_fn=schema_fn,
            close_fn=self._engine.interrupt,
        )

    @property
    def _cancel(self) -> Callable[[], None]:
        return self._engine.interrupt


class EngineRegistry:
    def available_engines(self) -> tuple[EngineDescriptor, ...]:
        engines: list[EngineDescriptor] = [
            EngineDescriptor(kind=EngineKind.DUCKDB, display_name="DuckDB", available=True),
            self._spark_descriptor(),
        ]
        return tuple(engines)

    def create(self, kind: EngineKind, request_id: UUID) -> ExecutionEngine:
        if kind is EngineKind.DUCKDB:
            return _DuckDBAdapter(request_id)

        if kind is EngineKind.SPARK:
            if not self._is_spark_available():
                raise EngineUnavailableError(
                    "Spark engine is unavailable because pyspark is not installed"
                )
            return _SparkAdapter(request_id)

        raise ValueError(f"Unsupported engine kind: {kind}")

    def _is_spark_available(self) -> bool:
        return util.find_spec("pyspark") is not None

    def _spark_descriptor(self) -> EngineDescriptor:
        if self._is_spark_available():
            return EngineDescriptor(
                kind=EngineKind.SPARK,
                display_name="Spark",
                available=True,
            )

        return EngineDescriptor(
            kind=EngineKind.SPARK,
            display_name="Spark",
            available=False,
            unavailable_reason="pyspark is not installed",
        )


def _frame_to_columns(frame: pl.DataFrame) -> tuple[ColumnSchema, ...] | None:
    if frame.height == 0:
        return ()
    columns: list[ColumnSchema] = []
    rows = frame.rows(named=True)
    for row in rows:
        columns.append(
            ColumnSchema(
                name=str(row.get("Column")),
                data_type=str(row.get("Type")),
            )
        )
    return tuple(columns)


__all__ = ["EngineDescriptor", "EngineRegistry", "EngineUnavailableError"]
