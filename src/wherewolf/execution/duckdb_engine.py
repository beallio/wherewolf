import duckdb
import time
import pandas as pd
from .models import QueryResult


class DuckDBEngine:
    """Execution engine using DuckDB."""

    def __init__(self):
        self.con = duckdb.connect(database=":memory:")

    def _register_view(self, path: str):
        """Registers the dataset as a view named 'dataset'."""
        from pathlib import Path

        abs_path = Path(path).expanduser().resolve()
        suffix = abs_path.suffix.lower()
        if suffix == ".csv":
            rel_source = self.con.from_csv_auto(str(abs_path))
        elif suffix == ".parquet":
            rel_source = self.con.from_parquet(str(abs_path))
        elif suffix == ".json":
            rel_source = self.con.sql("SELECT * FROM read_json_auto(?)", params=[str(abs_path)])
        elif suffix in [".xlsx", ".xls"]:
            self.con.execute("INSTALL excel; LOAD excel;")
            rel_source = self.con.sql("SELECT * FROM read_xlsx(?)", params=[str(abs_path)])
        else:
            rel_source = self.con.from_csv_auto(str(abs_path))

        rel_source.create_view("dataset", replace=True)

    def get_schema(self, path: str) -> pd.DataFrame:
        """Returns the schema of the dataset.

        Returns:
            A DataFrame with 'Column' and 'Type' columns.
        """
        try:
            self._register_view(path)
            # DESCRIBE dataset returns: column_name, column_type, null, key, default, extra
            df = self.con.sql("DESCRIBE dataset").df()
            # Normalize to Column/Type
            return df[["column_name", "column_type"]].rename(
                columns={"column_name": "Column", "column_type": "Type"}
            )
        except Exception:
            return pd.DataFrame({"Column": [], "Type": []})

    def execute(self, query: str, path: str, limit: int = 1000) -> QueryResult:
        """Executes a SQL query against a local file using DuckDB.

        Args:
            query: The SQL query to execute.
            path: The filesystem path to the data file.
            limit: Maximum number of rows to return in the preview.

        Returns:
            A QueryResult object.
        """
        start_time = time.time()
        try:
            # 1. Register the dataset view
            self._register_view(path)

            # 2. Execute the user query
            # We wrap the user query to handle limits for the preview
            # Note: The user query must refer to 'dataset'
            rel = self.con.sql(query)

            # 3. Fetch the preview + 1 extra row
            df_preview_plus_one = rel.limit(limit + 1).df()

            # 4. Extract results
            df_preview = df_preview_plus_one.head(limit)
            row_count = len(df_preview)
            is_truncated = len(df_preview_plus_one) > limit

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
        """Interrupts the current query execution."""
        if self.con:
            self.con.interrupt()
