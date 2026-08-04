from __future__ import annotations

import time
from importlib import import_module, util
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import polars as pl

from .models import QueryResult

SPARK_AVAILABLE = util.find_spec("pyspark") is not None


class SparkEngine:
    """Execute a request in an isolated SQL session on the shared local Spark context."""

    def __init__(self, request_id: UUID | None = None) -> None:
        self._request_id = request_id or uuid4()
        self.spark: Any | None = None
        self._active_views: set[str] = set()

    def _get_session(self) -> Any:
        """Start Spark only on demand and use a fresh SQL session for this request."""
        if self.spark is not None:
            return self.spark
        if not SPARK_AVAILABLE:
            raise RuntimeError("PySpark is not installed; install wherewolf[spark]")

        try:
            spark_session = import_module("pyspark.sql").SparkSession
            root_session = (
                # pyspark exposes `builder` dynamically, which ty cannot resolve.
                spark_session.builder.appName("Wherewolf")  # ty: ignore[unresolved-attribute]
                .master("local[1]")
                .config("spark.driver.memory", "512m")
                .config("spark.ui.enabled", "false")
                .config("spark.sql.shuffle.partitions", "1")
                .config("spark.sql.execution.arrow.pyspark.enabled", "true")
                .getOrCreate()
            )
            # `getOrCreate` reuses the one JVM-backed context. A child SQL session keeps
            # temporary views isolated between request adapters while sharing that context.
            self.spark = root_session.newSession()
        except Exception as error:  # Startup boundary: normalize JVM failures.
            raise RuntimeError(
                "Unable to start Spark. Install wherewolf[spark] and a compatible Java runtime. "
                f"Details: {error}"
            ) from error
        return self.spark

    @staticmethod
    def _validate_json_shape(path: Path) -> None:
        """Keep the suffix contract explicit instead of silently misreading JSON input.

        `.json` is a JSON array and `.jsonl` is one JSON object per line. This small
        content check catches the common accidental suffix swap before Spark can return
        a plausible-but-wrong frame.
        """
        try:
            leading = path.read_text(encoding="utf-8").lstrip()[:1]
        except OSError as error:
            raise ValueError(f"Cannot read JSON input {path}: {error}") from error

        if path.suffix.lower() == ".json" and leading != "[":
            raise ValueError("JSON files must contain a JSON array; use .jsonl for JSON Lines")
        if path.suffix.lower() == ".jsonl" and leading == "[":
            raise ValueError(
                "JSON Lines files must contain one object per line; use .json for arrays"
            )

    def _register_view(self, path: str, alias: str = "dataset") -> Any:
        """Read one source and make it available for the current request only."""
        spark = self._get_session()
        abs_path = Path(path).expanduser().resolve()
        suffix = abs_path.suffix.lower()

        if suffix == ".csv":
            df_spark = (
                spark.read.option("header", "true").option("inferSchema", "true").csv(str(abs_path))
            )
        elif suffix == ".parquet":
            df_spark = spark.read.parquet(str(abs_path))
        elif suffix in {".json", ".jsonl"}:
            self._validate_json_shape(abs_path)
            df_spark = spark.read.option("multiLine", str(suffix == ".json").lower()).json(
                str(abs_path)
            )
        elif suffix in {".xlsx", ".xls"}:
            df_spark = spark.createDataFrame(pl.read_excel(abs_path).to_arrow())
        else:
            raise ValueError(f"Unsupported file format for path: {abs_path}")

        df_spark.createOrReplaceTempView(alias)
        self._active_views.add(alias)
        return df_spark

    def _drop_active_views(self) -> None:
        if self.spark is None:
            return
        for alias in self._active_views:
            try:
                self.spark.catalog.dropTempView(alias)
            except Exception:  # noqa: BLE001, S110  # Cleanup is best effort after a failed job.
                pass
        self._active_views.clear()

    def get_schema(self, path: str) -> pl.DataFrame:
        """Return schema columns or raise so the registry can report a schema error."""
        if not SPARK_AVAILABLE:
            return pl.DataFrame(schema={"Column": pl.Utf8, "Type": pl.Utf8})

        try:
            df_spark = self._register_view(path, alias="_schema_hud")
            return pl.DataFrame(
                [
                    {"Column": field.name, "Type": field.dataType.simpleString()}
                    for field in df_spark.schema
                ],
                schema={"Column": pl.Utf8, "Type": pl.Utf8},
            )
        finally:
            self._drop_active_views()

    def execute(
        self,
        query: str,
        path: str = "",
        limit: int | None = 1000,
        catalog: dict[str, str] | None = None,
    ) -> QueryResult:
        if not SPARK_AVAILABLE:
            return QueryResult(success=False, error_message="PySpark not installed")

        start_time = time.time()
        try:
            spark = self._get_session()
            spark.sparkContext.setJobGroup(
                str(self._request_id),
                f"Wherewolf request {self._request_id}",
                interruptOnCancel=True,
            )

            active_catalog = dict(catalog or {})
            if path and "dataset" not in active_catalog:
                active_catalog["dataset"] = path
            for alias, dataset_path in active_catalog.items():
                self._register_view(dataset_path, alias=alias)

            res_spark = spark.sql(query)
            if limit is None:
                df_preview = cast(pl.DataFrame, pl.from_arrow(res_spark.toArrow()))
                row_count = len(df_preview)
                is_truncated = False
            else:
                preview_plus_one = cast(
                    pl.DataFrame, pl.from_arrow(res_spark.limit(limit + 1).toArrow())
                )
                df_preview = preview_plus_one.head(limit)
                row_count = len(df_preview)
                is_truncated = len(preview_plus_one) > limit

            return QueryResult(
                df=df_preview,
                execution_time=time.time() - start_time,
                row_count=row_count,
                success=True,
                is_truncated=is_truncated,
            )
        except Exception as error:  # noqa: BLE001  # Execution boundary: normalize Spark failures.
            return QueryResult(
                success=False,
                error_message=str(error),
                execution_time=time.time() - start_time,
            )
        finally:
            self._drop_active_views()

    def interrupt(self) -> None:
        """Cancel only this request's job group, never every Spark job in the context."""
        if self.spark is not None:
            spark_context = getattr(self.spark, "sparkContext", None)
            if spark_context is not None:
                spark_context.cancelJobGroup(str(self._request_id))
