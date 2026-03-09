import time
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
        if SPARK_AVAILABLE:
            # Note: We'll lazily create the session or expect it in the execute
            pass

    def _get_session(self):
        if not self.spark:
            self.spark = SparkSession.builder.appName("Wherewolf").master("local[*]").getOrCreate()
        return self.spark

    def execute(self, query: str, path: str, limit: int = 1000) -> QueryResult:
        if not SPARK_AVAILABLE:
            return QueryResult(success=False, error_message="PySpark not installed")

        import os

        abs_path = os.path.abspath(path)
        start_time = time.time()
        try:
            spark = self._get_session()

            # 1. Read the dataset
            # Determine format by extension (basic detection)
            if abs_path.endswith(".csv"):
                df_spark = (
                    spark.read.option("header", "true").option("inferSchema", "true").csv(abs_path)
                )
            elif abs_path.endswith(".parquet"):
                df_spark = spark.read.parquet(abs_path)
            elif abs_path.endswith(".json"):
                df_spark = spark.read.json(abs_path)
            else:
                # Default to automatic detection if supported,
                # but Spark is less automatic than DuckDB
                raise ValueError(f"Unsupported file format for path: {abs_path}")

            # 2. Register temp view
            df_spark.createOrReplaceTempView("dataset")

            # 3. Execute query
            res_spark = spark.sql(query)

            # 4. Get count
            row_count = res_spark.count()

            # 5. Preview
            # Using limit to avoid fetching everything
            df_preview = res_spark.limit(limit).toPandas()

            execution_time = time.time() - start_time
            return QueryResult(
                df=df_preview, execution_time=execution_time, row_count=row_count, success=True
            )
        except Exception as e:
            return QueryResult(
                success=False, error_message=str(e), execution_time=time.time() - start_time
            )

    def interrupt(self):
        """Interrupts current Spark job."""
        if self.spark:
            # Spark context interrupt
            self.spark.sparkContext.cancelAllJobs()
