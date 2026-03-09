from dataclasses import dataclass, field
import pandas as pd


@dataclass
class QueryResult:
    """Represents the results of a SQL query execution."""

    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    execution_time: float = 0.0
    row_count: int = 0
    success: bool = True
    error_message: str = ""
