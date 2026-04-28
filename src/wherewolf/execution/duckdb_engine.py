import duckdb
import time
import pandas as pd
from typing import Optional
from .models import QueryResult


class DuckDBEngine:
    """Execution engine using DuckDB."""

    def __init__(self):
        self.con = duckdb.connect(database=":memory:")
        self._registered_views = {}  # alias -> path mapping for idempotency

    def _register_view(self, path: str, alias: str = "dataset"):
        """Registers a dataset as a view with the given alias."""
        # Idempotency check
        if self._registered_views.get(alias) == path:
            return

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
            # Fallback for other extensions if somehow passed
            rel_source = self.con.from_csv_auto(str(abs_path))

        rel_source.create_view(alias, replace=True)
        self._registered_views[alias] = path

    def get_schema(self, path: str) -> pd.DataFrame:
        """Returns the schema of the dataset.

        Returns:
            A DataFrame with 'Column' and 'Type' columns.
        """
        try:
            # We use a temporary alias for schema HUD to avoid polluting the main query namespace
            temp_alias = "_schema_hud"
            self._register_view(path, alias=temp_alias)
            # DESCRIBE returns: column_name, column_type, null, key, default, extra
            df = self.con.sql(f"DESCRIBE {temp_alias}").df()
            # Normalize to Column/Type
            return df[["column_name", "column_type"]].rename(
                columns={"column_name": "Column", "column_type": "Type"}
            )
        except Exception:
            return pd.DataFrame({"Column": [], "Type": []})

    def execute(
        self,
        query: str,
        path: str = "",
        limit: int = 1000,
        catalog: Optional[dict[str, str]] = None,
    ) -> QueryResult:
        """Executes a SQL query against local files using DuckDB.

        Args:
            query: The SQL query to execute.
            path: Legacy single-file path (deprecated).
            limit: Maximum number of rows to return in the preview.
            catalog: A mapping of aliases to filesystem paths.

        Returns:
            A QueryResult object.
        """
        start_time = time.time()
        try:
            # 1. Prepare Catalog
            # Handle legacy 'path' parameter by wrapping it in a default catalog
            active_catalog = catalog or {}
            if path and "dataset" not in active_catalog:
                active_catalog["dataset"] = path

            # 2. Register all datasets in the catalog
            for alias, dataset_path in active_catalog.items():
                self._register_view(dataset_path, alias=alias)

            # 3. Execute the user query
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
