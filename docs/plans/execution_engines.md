# Plan: Execution Engines

## Problem Definition
Support multiple query engines (DuckDB, Spark) with a unified interface to execute SQL queries against local files.

## Architecture Overview
-   **EngineInterface (Base Class):** Defines the common API for all engines.
-   **DuckDBEngine:** Local, in-memory/in-process execution.
-   **SparkEngine:** Local PySpark cluster execution.
-   **EngineFactory:** Utility to instantiate the correct engine based on user selection.

## Core Data Structures
-   **QueryResult:**
    ```python
    @dataclass
    class QueryResult:
        df: pd.DataFrame
        execution_time: float
        row_count: int
        success: bool = True
        error_message: str = ""
    ```

## Public Interfaces
-   `Engine.execute(query: str, path: str, limit: int = 1000) -> QueryResult`
-   `Engine.interrupt()` (for cancellation)

## Implementation Strategy
1.  **DuckDB:**
    -   Register the filesystem path as a temporary view named `dataset`.
    -   Execute the query via `duckdb.sql()`.
    -   Use `fetchdf()` for the preview.
2.  **Spark:**
    -   Check for existing `SparkSession` or create a new local one.
    -   Read the file (detecting CSV/Parquet/JSON) and register it as a temp view `dataset`.
    -   Execute the query via `spark.sql()`.
    -   Use `limit(n).toPandas()` for the preview.

## Testing Strategy (RED)
1.  Create `tests/test_engines.py`.
2.  Test `DuckDBEngine` with a small CSV file.
3.  Test `SparkEngine` with a small Parquet file (mocking or using a temporary session).
4.  Verify `QueryResult` structure.
5.  Verify the reserved table name `dataset` works.
