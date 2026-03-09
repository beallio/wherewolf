import duckdb
import time
from .models import QueryResult


class DuckDBEngine:
    """Execution engine using DuckDB."""

    def __init__(self):
        self.con = duckdb.connect(database=":memory:")

    def execute(self, query: str, path: str, limit: int = 1000) -> QueryResult:
        """Executes a SQL query against a local file using DuckDB.

        Args:
            query: The SQL query to execute.
            path: The filesystem path to the data file.
            limit: Maximum number of rows to return in the preview.

        Returns:
            A QueryResult object.
        """
        import os

        abs_path = os.path.abspath(path)
        start_time = time.time()
        try:
            # 1. Register the dataset view
            # DuckDB automatically detects CSV, Parquet, JSON based on extension or content
            self.con.execute(f"CREATE OR REPLACE VIEW dataset AS SELECT * FROM '{abs_path}'")

            # 2. Execute the user query
            # We wrap the user query to handle limits for the preview
            # Note: The user query must refer to 'dataset'
            rel = self.con.sql(query)

            # 3. Get total row count (might be expensive for large datasets,
            # but usually okay for local DuckDB)
            row_count = rel.count("*").fetchone()[0]

            # 4. Fetch the preview DataFrame
            df = rel.limit(limit).df()

            execution_time = time.time() - start_time
            return QueryResult(
                df=df, execution_time=execution_time, row_count=row_count, success=True
            )
        except Exception as e:
            return QueryResult(
                success=False, error_message=str(e), execution_time=time.time() - start_time
            )

    def interrupt(self):
        """Interrupts the current query execution."""
        if self.con:
            self.con.interrupt()
