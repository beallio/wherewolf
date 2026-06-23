from dataclasses import dataclass, field
import polars as pl


@dataclass
class QueryResult:
    """Represents the results of a SQL query execution."""

    df: pl.DataFrame = field(default_factory=pl.DataFrame)
    execution_time: float = 0.0
    row_count: int = 0
    success: bool = True
    error_message: str = ""
    is_truncated: bool = False
