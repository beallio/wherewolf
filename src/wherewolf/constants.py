"""Central constants for the Wherewolf application."""

# UI engine/dialect display name -> sqlglot dialect identifier
DIALECT_MAPPING = {
    "DuckDB": "duckdb",
    "Spark": "spark",
    "Azure SQL": "tsql",
    "Oracle": "oracle",
    "PostgreSQL": "postgres",
}
