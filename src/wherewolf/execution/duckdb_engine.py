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
        from pathlib import Path

        abs_path = Path(path).expanduser().resolve()
        start_time = time.time()
        try:
            # 1. Register the dataset view
            # DuckDB automatically detects CSV, Parquet, JSON based on extension or content
            # Using Relation API to safely handle paths with special characters
            suffix = abs_path.suffix.lower()
            if suffix == ".csv":
                rel_source = self.con.from_csv_auto(str(abs_path))
            elif suffix == ".parquet":
                rel_source = self.con.from_parquet(str(abs_path))
            elif suffix == ".json":
                # read_json_auto doesn't have a direct 'from_json_auto' in all versions
                # so we can use the sql method with a Relation
                rel_source = self.con.read_json_auto(str(abs_path))
            else:
                # Fallback to auto-detection
                rel_source = self.con.from_csv_auto(str(abs_path))

            rel_source.create_view("dataset", replace=True)

            # 2. Execute the user query
            # We wrap the user query to handle limits for the preview
            # Note: The user query must refer to 'dataset'
            rel = self.con.sql(query)

            # 3. Get total row count (might be expensive for large datasets,
            # but usually okay for local DuckDB)
            res = rel.count("*").fetchone()
            row_count = int(res[0]) if res else 0

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
