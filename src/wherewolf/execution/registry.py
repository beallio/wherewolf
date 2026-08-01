from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
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
from wherewolf.services.export_destination import ExportFormat, write_atomically

FULL_XLSX_ROW_LIMIT = 100_000


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


class _DuckDBAdapter(ExecutionEngine):
    def __init__(self, request_id: UUID):
        self._request_id = request_id
        self._con = None
        self._cancelled = False

    def cancellation_handle(self) -> CancellationHandle:
        return _CancellationHandle(request_id=self._request_id, _cancel=self.interrupt)

    def interrupt(self) -> None:
        self._cancelled = True
        if self._con is not None:
            self._con.interrupt()

    def close(self) -> None:
        self.interrupt()

    def _register_view(self, con, path_str: str, alias: str) -> None:
        from pathlib import Path

        abs_path = Path(path_str).expanduser().resolve()
        suffix = abs_path.suffix.lower()
        if suffix == ".csv":
            rel_source = con.from_csv_auto(str(abs_path))
        elif suffix == ".parquet":
            rel_source = con.from_parquet(str(abs_path))
        elif suffix == ".json":
            rel_source = con.sql("SELECT * FROM read_json_auto(?)", params=[str(abs_path)])
        elif suffix in [".xlsx", ".xls"]:
            con.execute("INSTALL excel; LOAD excel;")
            rel_source = con.sql("SELECT * FROM read_xlsx(?)", params=[str(abs_path)])
        else:
            rel_source = con.from_csv_auto(str(abs_path))

        rel_source.create_view(alias, replace=True)

    def execute_preview(self, request: ExecutionRequest) -> QueryResult:
        import time

        import duckdb

        start_time = time.time()
        if self._cancelled:
            return QueryResult(
                request_id=request.request_id,
                status=ExecutionStatus.CANCELLED,
                frame=None,
                execution_seconds=0.0,
                preview_row_count=0,
                total_row_count=None,
                truncated=False,
                completed_at=datetime.now(UTC),
            )

        con = duckdb.connect(database=":memory:")
        self._con = con

        try:
            if self._cancelled:
                con.interrupt()

            for binding in request.catalog:
                self._register_view(con, str(binding.path), binding.alias)

            rel = con.sql(request.executable_sql)

            limit = request.preview_limit
            df_plus_one = rel.limit(limit + 1).pl()
            df_preview = df_plus_one.head(limit)
            row_count = len(df_preview)
            is_truncated = len(df_plus_one) > limit
            execution_time = time.time() - start_time

            if self._cancelled:
                return QueryResult(
                    request_id=request.request_id,
                    status=ExecutionStatus.CANCELLED,
                    frame=None,
                    execution_seconds=execution_time,
                    preview_row_count=0,
                    total_row_count=None,
                    truncated=False,
                    completed_at=datetime.now(UTC),
                )

            return QueryResult(
                request_id=request.request_id,
                status=ExecutionStatus.SUCCEEDED,
                frame=df_preview,
                execution_seconds=execution_time,
                preview_row_count=row_count,
                total_row_count=None,
                truncated=is_truncated,
                completed_at=datetime.now(UTC),
            )
        except Exception as e:  # noqa: BLE001  # Execution boundary: normalize runtime errors into failed QueryResult
            execution_time = time.time() - start_time
            if (
                self._cancelled
                or isinstance(e, duckdb.InterruptException)
                or "interrupt" in str(e).lower()
            ):
                return QueryResult(
                    request_id=request.request_id,
                    status=ExecutionStatus.CANCELLED,
                    frame=None,
                    execution_seconds=execution_time,
                    preview_row_count=0,
                    total_row_count=None,
                    truncated=False,
                    completed_at=datetime.now(UTC),
                )

            return QueryResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                frame=None,
                execution_seconds=execution_time,
                preview_row_count=0,
                total_row_count=None,
                truncated=False,
                completed_at=datetime.now(UTC),
                error_type=type(e).__name__,
                error_message=str(e),
            )
        finally:
            self._con = None
            try:
                con.close()
            except Exception:  # noqa: BLE001, S110  # Cleanup boundary: ignore errors during connection closure
                pass

    def export_full(
        self, request: ExecutionRequest, destination: Path, export_format: str
    ) -> tuple[str, ...]:
        """Re-execute request SQL and stream CSV/Parquet directly through COPY."""
        import duckdb

        warnings = _source_warnings(request)
        if self._cancelled:
            raise RuntimeError("Export cancelled")
        con = duckdb.connect(database=":memory:")
        self._con = con
        try:
            for binding in request.catalog:
                self._register_view(con, str(binding.path), binding.alias)
            fmt = ExportFormat(export_format)
            if fmt is ExportFormat.XLSX:
                row = con.sql(f"SELECT count(*) FROM ({request.executable_sql})").fetchone()
                assert row is not None
                count = row[0]
                if count > FULL_XLSX_ROW_LIMIT:
                    raise ValueError(
                        f"Full XLSX export is limited to {FULL_XLSX_ROW_LIMIT:,} rows; use CSV or Parquet."
                    )

                def write_xlsx(path: Path) -> None:
                    con.sql(request.executable_sql).pl().write_excel(path)

                write_atomically(destination, write_xlsx)
            else:
                format_sql = "CSV" if fmt is ExportFormat.CSV else "PARQUET"

                def copy_to(path: Path) -> None:
                    escaped_temp = str(path).replace("'", "''")
                    con.execute(
                        f"COPY ({request.executable_sql}) TO '{escaped_temp}' (FORMAT {format_sql})"
                    )

                write_atomically(destination, copy_to)
            if self._cancelled:
                raise RuntimeError("Export cancelled")
            return warnings
        finally:
            self._con = None
            try:
                con.close()
            except Exception:  # noqa: BLE001, S110
                pass

    def inspect_schema(self, entry: CatalogEntry) -> SchemaResult:
        import duckdb

        if self._cancelled:
            return SchemaResult(
                entry_id=entry.id,
                columns=(),
                error_type="CancelledError",
                error_message="Schema inspection cancelled",
            )

        con = duckdb.connect(database=":memory:")
        self._con = con
        try:
            if self._cancelled:
                con.interrupt()

            temp_alias = "_schema_hud"
            self._register_view(con, str(entry.path), temp_alias)
            rows = con.sql(f"DESCRIBE {temp_alias}").fetchall()
            cols = tuple(
                ColumnSchema(
                    name=str(r[0]), data_type=str(r[1]), nullable=(str(r[2]).upper() == "YES")
                )
                for r in rows
            )
            return SchemaResult(
                entry_id=entry.id,
                columns=cols,
            )
        except Exception as e:  # noqa: BLE001  # Schema inspection boundary: return empty schema on error
            if (
                self._cancelled
                or isinstance(e, duckdb.InterruptException)
                or "interrupt" in str(e).lower()
            ):
                return SchemaResult(
                    entry_id=entry.id,
                    columns=(),
                    error_type="CancelledError",
                    error_message="Schema inspection cancelled",
                )
            return SchemaResult(
                entry_id=entry.id,
                columns=(),
                error_type=type(e).__name__,
                error_message=str(e),
            )
        finally:
            self._con = None
            try:
                con.close()
            except Exception:  # noqa: BLE001, S110  # Cleanup boundary: ignore errors during connection closure
                pass


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

    def export_full(
        self, request: ExecutionRequest, destination: Path, export_format: str
    ) -> tuple[str, ...]:
        raise ValueError("Full export is currently available only for DuckDB")


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


def _source_warnings(request: ExecutionRequest) -> tuple[str, ...]:
    """Report source mutation without blocking an explicit export request."""
    warnings: list[str] = []
    for snapshot in request.source_snapshots:
        try:
            stat = snapshot.path.stat()
        except OSError:
            warnings.append(f"Source changed or is unavailable: {snapshot.path}")
            continue
        if stat.st_size != snapshot.size or stat.st_mtime_ns != snapshot.mtime_ns:
            warnings.append(f"Source changed since query ran: {snapshot.path}")
    return tuple(warnings)


__all__ = ["EngineDescriptor", "EngineRegistry", "EngineUnavailableError"]
