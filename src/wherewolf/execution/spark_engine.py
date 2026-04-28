import time
import pandas as pd
from typing import Optional
from .models import QueryResult

try:
    from pyspark.sql import SparkSession

    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False


class SparkEngine:
    """Execution engine using PySpark."""

    def __init__(self):
        self.spark = None
        self._registered_views = {}  # alias -> path mapping for idempotency
        if SPARK_AVAILABLE:
            # Note: We'll lazily create the session or expect it in the execute
            pass

    def _get_session(self):
        if not self.spark:
            self.spark = SparkSession.builder.appName("Wherewolf").master("local[*]").getOrCreate()
        return self.spark

    def _register_view(self, path: str, alias: str = "dataset"):
        """Registers a dataset as a view with the given alias."""
        # Idempotency check
        if self._registered_views.get(alias) == path:
            # We still need the dataframe for get_schema if we just registered it
            # But for execute, we just need the view to exist.
            # To be safe, we'll re-read if it's not in the spark catalog,
            # but usually it's faster to trust self._registered_views.
            pass

        import os
        from pathlib import Path

        spark = self._get_session()
        abs_path = os.path.abspath(path)
        suffix = Path(abs_path).suffix.lower()

        # Determine format by extension (basic detection)
        if suffix == ".csv":
            df_spark = (
                spark.read.option("header", "true").option("inferSchema", "true").csv(abs_path)
            )
        elif suffix == ".parquet":
            df_spark = spark.read.parquet(abs_path)
        elif suffix == ".json":
            df_spark = spark.read.json(abs_path)
        elif suffix in [".xlsx", ".xls"]:
            # Use pandas as a bridge for Excel in local Spark
            df_pd = pd.read_excel(abs_path)
            df_spark = spark.createDataFrame(df_pd)
        else:
            raise ValueError(f"Unsupported file format for path: {abs_path}")

        # 2. Register temp view
        df_spark.createOrReplaceTempView(alias)
        self._registered_views[alias] = path
        return df_spark

    def get_schema(self, path: str) -> pd.DataFrame:
        """Returns the schema of the dataset.

        Returns:
            A DataFrame with 'Column' and 'Type' columns.
        """
        if not SPARK_AVAILABLE:
            return pd.DataFrame({"Column": [], "Type": []})

        try:
            temp_alias = "_schema_hud"
            df_spark = self._register_view(path, alias=temp_alias)
            # Spark schema to pandas
            schema_data = []
            for field in df_spark.schema:
                schema_data.append({"Column": field.name, "Type": field.dataType.simpleString()})
            return pd.DataFrame(schema_data)
        except Exception:
            return pd.DataFrame({"Column": [], "Type": []})

    def execute(
        self,
        query: str,
        path: str = "",
        limit: int = 1000,
        catalog: Optional[dict[str, str]] = None,
    ) -> QueryResult:
        if not SPARK_AVAILABLE:
            return QueryResult(success=False, error_message="PySpark not installed")

        start_time = time.time()
        try:
            spark = self._get_session()

            # 1. Prepare Catalog
            active_catalog = catalog or {}
            if path and "dataset" not in active_catalog:
                active_catalog["dataset"] = path

            # 2. Register all datasets in the catalog
            for alias, dataset_path in active_catalog.items():
                self._register_view(dataset_path, alias=alias)

            # 3. Execute query
            res_spark = spark.sql(query)

            # 4. Fetch the preview + 1 extra row to see if there's more
            # This avoids a full scan of the dataset with count()
            preview_plus_one = res_spark.limit(limit + 1).toPandas()

            # 5. Extract results
            df_preview = preview_plus_one.head(limit)
            row_count = len(df_preview)
            is_truncated = len(preview_plus_one) > limit

            execution_time = time.time() - start_time
            return QueryResult(
                df=df_preview,
                execution_time=execution_time,
                row_count=row_count,
                success=True,
                is_truncated=is_truncated,
            )
        except Exception as e:
            return QueryResult(
                success=False, error_message=str(e), execution_time=time.time() - start_time
            )

    def interrupt(self):
        """Interrupts current Spark job."""
        if self.spark:
            # Spark context interrupt
            sc = getattr(self.spark, "sparkContext", None)
            if sc:
                sc.cancelAllJobs()
