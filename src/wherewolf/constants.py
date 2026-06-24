"""Central constants for the Wherewolf application."""

# Supported data file extensions for the workbench
SUPPORTED_EXTENSIONS = {".csv", ".parquet", ".json", ".xlsx", ".xls"}

# UI engine/dialect display name -> sqlglot dialect identifier
DIALECT_MAPPING = {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}
