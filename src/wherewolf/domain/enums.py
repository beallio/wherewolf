from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from wherewolf.domain.errors import UnsupportedFormatError


class EngineKind(StrEnum):
    DUCKDB = "duckdb"
    SPARK = "spark"


class SourceFormat(StrEnum):
    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"
    JSON_LINES = "jsonl"
    XLSX = "xlsx"

    @classmethod
    def from_path(cls, path: Path) -> SourceFormat:
        suffix = path.suffix.lower()
        match suffix:
            case ".csv":
                return cls.CSV
            case ".parquet":
                return cls.PARQUET
            case ".json":
                return cls.JSON
            case ".jsonl":
                return cls.JSON_LINES
            case ".xlsx":
                return cls.XLSX
            case _:
                raise UnsupportedFormatError(f"Unsupported source format: {suffix}")


class ExecutionStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    CANCELLATION_REQUESTED = "cancellation_requested"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CompletionKind(StrEnum):
    TABLE = "table"
    CTE = "cte"
    COLUMN = "column"
    FUNCTION = "function"
    KEYWORD = "keyword"
    SNIPPET = "snippet"


SQLGLot_DIALECT_BY_ENGINE = {
    EngineKind.DUCKDB: "duckdb",
    EngineKind.SPARK: "spark",
}
