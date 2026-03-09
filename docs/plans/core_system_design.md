# Plan: Wherewolf Core System Design

## Problem Definition
Provide a local, production-grade SQL workbench that allows users to query local files (CSV, Parquet, JSON) using either DuckDB or Spark, with real-time SQL translation between dialects, execution metrics, and history persistence.

## Architecture Overview
The application will follow a modular multi-layered architecture:
1.  **UI Layer (Streamlit):** Handles user input, sidebar configuration, and result rendering.
2.  **Execution Layer:** Abstracts the backend engines (DuckDB, Spark) using a unified interface.
3.  **Translation Layer (SQLGlot):** Handles transpilation between DuckDB and SparkSQL dialects.
4.  **Storage Layer:** Manages local history persistence at `~/.wherewolf/history.json`.
5.  **Export Layer:** Handles data conversion to CSV, Excel, and Parquet via Pandas/PyArrow.

## Core Data Structures
-   **QueryResult:** A dataclass containing the DataFrame (or a preview slice), execution time, row count, and success/failure status.
-   **HistoryEntry:** A Pydantic model or TypedDict: `{timestamp: str, engine: str, query: str, path: str}`.
-   **EngineConfig:** Configuration for SparkSession or DuckDB connection strings.

## Public Interfaces
-   `EngineInterface.execute(query: str, path: str) -> QueryResult`
-   `Translator.translate(query: str, from_dialect: str, to_dialect: str) -> str`
-   `HistoryManager.save(entry: HistoryEntry)`
-   `Exporter.to_format(df: pd.DataFrame, format: str) -> bytes`

## Dependency Requirements
-   `streamlit`, `duckdb`, `pyspark`, `ibis-framework`, `sqlglot`, `pandas`, `pyarrow`, `openpyxl`.

## Testing Strategy
-   **Unit Tests:** Test `Translator` logic for dialect conversion.
-   **Integration Tests:** Verify `DuckDB` and `Spark` engines can read a sample Parquet/CSV file and return a predictable DataFrame.
-   **Mocking:** Use mock filesystem paths for history storage tests.
-   **TDD:** Create `tests/test_engine.py` and `tests/test_translation.py` before implementation.

## Technical Decisions
-   **SQL Syntax:** To simplify user experience, the query will assume a reserved table name `dataset` (e.g., `SELECT * FROM dataset`). The engine will dynamically map `dataset` to the provided file path.
-   **Threaded Execution:** Use `concurrent.futures.ThreadPoolExecutor` to run queries. This allows the Streamlit UI to remain responsive and provides a hook for cancellation (though Python threads are not natively "stoppable," engine-specific interrupts like `duckdb_connection.interrupt()` will be used).
-   **Ibis Role:** Ibis will be used as the primary execution wrapper to maintain a consistent API across engines.
