from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from shutil import which
from uuid import UUID

import polars as pl

# LOAD-BEARING: do not remove, and do not make this lazy.
#
# DuckDB loads pyarrow on demand during `relation.pl()`. pyarrow's bundled mimalloc
# initialises a thread-local heap on libarrow's first allocation, and if that first
# allocation happens on a secondary thread, `mi_thread_init` segfaults for every
# subsequent thread once that one exits. The desktop app runs each query on a fresh
# QThread, so the *second* query killed the process.
#
# Importing pyarrow here — at module scope, on the main thread, at startup — pins that
# initialisation to a thread that outlives every worker. A bare import is sufficient.
# Guarded by tests/test_arrow_thread_init_crash.py.
import pyarrow  # noqa: F401

from wherewolf.domain import (
    CatalogEntry,
    ColumnProfile,
    ColumnSchema,
    EngineKind,
    EngineUnavailableError,
    ExecutionRequest,
    ExecutionStatus,
    ProfileResult,
    QueryResult,
    SchemaResult,
)
from wherewolf.execution.base import CancellationHandle, ExecutionEngine
from wherewolf.services.export_destination import ExportFormat, write_atomically
from wherewolf.services.identifier_quoting import quote_identifier

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

            rel = con.sql(request.executable_sql, params=list(request.parameters))

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

    def profile_dataset(self, entry: CatalogEntry) -> ProfileResult:
        """Run DuckDB's full-scan SUMMARIZE statement for one catalog entry."""
        import duckdb

        if self._cancelled:
            return ProfileResult(
                entry_id=entry.id,
                profiles=(),
                error_type="CancelledError",
                error_message="Dataset profiling cancelled",
            )

        con = duckdb.connect(database=":memory:")
        self._con = con
        try:
            if self._cancelled:
                con.interrupt()

            temp_alias = "_profile_hud"
            self._register_view(con, str(entry.path), temp_alias)
            rows = con.sql(f"SUMMARIZE {temp_alias}").fetchall()
            profiles = tuple(
                ColumnProfile(
                    name=str(row[0]),
                    data_type=str(row[1]),
                    min=_as_text(row[2]),
                    max=_as_text(row[3]),
                    approx_unique=_as_int(row[4]),
                    avg=_as_text(row[5]),
                    std=_as_text(row[6]),
                    q25=_as_text(row[7]),
                    q50=_as_text(row[8]),
                    q75=_as_text(row[9]),
                    count=_as_int(row[10]),
                    null_percentage=_as_float(row[11]),
                )
                for row in rows
            )
            return ProfileResult(entry_id=entry.id, profiles=profiles)
        except Exception as error:  # noqa: BLE001  # Profiling boundary normalizes engine failures.
            if (
                self._cancelled
                or isinstance(error, duckdb.InterruptException)
                or "interrupt" in str(error).lower()
            ):
                return ProfileResult(
                    entry_id=entry.id,
                    profiles=(),
                    error_type="CancelledError",
                    error_message="Dataset profiling cancelled",
                )
            return ProfileResult(
                entry_id=entry.id,
                profiles=(),
                error_type=type(error).__name__,
                error_message=str(error),
            )
        finally:
            self._con = None
            try:
                con.close()
            except Exception:  # noqa: BLE001, S110  # Cleanup boundary: ignore errors during connection closure
                pass

    def value_counts(
        self, entry: CatalogEntry, column_name: str, limit: int
    ) -> tuple[tuple[tuple[object, int], ...], int, int]:
        """Return top grouped values, distinct count, and total row count."""
        import duckdb

        con = duckdb.connect(database=":memory:")
        self._con = con
        try:
            self._register_view(con, str(entry.path), entry.alias)
            column_sql = quote_identifier(column_name)
            alias_sql = quote_identifier(entry.alias)
            rows = con.execute(
                f"SELECT {column_sql}, count(*) FROM {alias_sql} "
                "GROUP BY 1 ORDER BY 2 DESC LIMIT ?",
                [max(1, int(limit))],
            ).fetchall()
            distinct_row = con.execute(
                f"SELECT count(DISTINCT {column_sql}) FROM {alias_sql}"
            ).fetchone()
            total_row = con.execute(f"SELECT count(*) FROM {alias_sql}").fetchone()
            if distinct_row is None or total_row is None:
                raise RuntimeError("DuckDB returned no value-count totals")
            total_distinct = distinct_row[0]
            total_rows = total_row[0]
            return (
                tuple((row[0], int(row[1])) for row in rows),
                int(total_distinct),
                int(total_rows),
            )
        finally:
            self._con = None
            con.close()

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
                row = con.execute(
                    f"SELECT count(*) FROM ({request.executable_sql})", request.parameters
                ).fetchone()
                assert row is not None
                count = row[0]
                if count > FULL_XLSX_ROW_LIMIT:
                    raise ValueError(
                        f"Full XLSX export is limited to {FULL_XLSX_ROW_LIMIT:,} rows; use CSV or Parquet."
                    )

                def write_xlsx(path: Path) -> None:
                    con.execute(request.executable_sql, request.parameters).pl().write_excel(path)

                write_atomically(destination, write_xlsx)
            else:
                format_sql = "CSV" if fmt is ExportFormat.CSV else "PARQUET"

                def copy_to(path: Path) -> None:
                    escaped_temp = str(path).replace("'", "''")
                    con.execute(
                        f"COPY ({request.executable_sql}) TO '{escaped_temp}' (FORMAT {format_sql})",
                        request.parameters,
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

        self._engine = SparkEngine(request_id=request_id)

        def execute_fn(request: ExecutionRequest) -> QueryResult:
            if request.parameters:
                return QueryResult(
                    request_id=request.request_id,
                    status=ExecutionStatus.FAILED,
                    frame=None,
                    execution_seconds=0.0,
                    preview_row_count=0,
                    total_row_count=None,
                    truncated=False,
                    completed_at=datetime.now(UTC),
                    error_type="unsupported_parameters",
                    error_message="Spark does not support bound query parameters",
                )
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
            try:
                schema = self._engine.get_schema(str(entry.path))
                return SchemaResult(entry_id=entry.id, columns=_frame_to_columns(schema))
            except Exception as error:  # noqa: BLE001  # Schema boundary: preserve the failure for the HUD.
                return SchemaResult(
                    entry_id=entry.id,
                    columns=(),
                    error_type=type(error).__name__,
                    error_message=str(error),
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

    def export_full(
        self, request: ExecutionRequest, destination: Path, export_format: str
    ) -> tuple[str, ...]:
        raise ValueError("Full export is currently available only for DuckDB")

    def profile_dataset(self, entry: CatalogEntry) -> ProfileResult:
        return ProfileResult(
            entry_id=entry.id,
            profiles=(),
            error_type="UnsupportedOperation",
            error_message="Profiling is not available for this engine (Spark).",
        )


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
                    f"Spark engine is unavailable because {self._spark_unavailable_reason()}"
                )
            return _SparkAdapter(request_id)

        raise ValueError(f"Unsupported engine kind: {kind}")

    def _is_spark_available(self) -> bool:
        return self._pyspark_available() and self._java_available()

    @staticmethod
    def _pyspark_available() -> bool:
        return util.find_spec("pyspark") is not None

    @staticmethod
    def _java_available() -> bool:
        return which("java") is not None

    def _spark_unavailable_reason(self) -> str:
        missing: list[str] = []
        if not self._pyspark_available():
            missing.append("pyspark is not installed; install wherewolf[spark]")
        if not self._java_available():
            missing.append("Java is not available on PATH")
        return " and ".join(missing)

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
            unavailable_reason=self._spark_unavailable_reason(),
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


def _as_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _as_int(value: object) -> int | None:
    return int(str(value)) if value is not None else None


def _as_float(value: object) -> float | None:
    return float(str(value)) if value is not None else None


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
