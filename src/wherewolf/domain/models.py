from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

import polars as pl

from wherewolf.domain.enums import CompletionKind, EngineKind, ExecutionStatus, SourceFormat


@dataclass(frozen=True, slots=True)
class CompletionContext:
    sql: str
    cursor_offset: int
    dialect: str
    catalog: tuple[CatalogEntry, ...]


@dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str
    insert_text: str
    kind: CompletionKind
    detail: str | None
    sort_key: tuple[int, str]

    def __post_init__(self):
        if not self.label:
            raise ValueError("empty label")


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool | None = None


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    id: UUID
    alias: str
    path: Path
    source_format: SourceFormat
    schema: tuple[ColumnSchema, ...] | None = None
    schema_error: str | None = None
    profile: tuple[ColumnProfile, ...] | None = None
    profile_error: str | None = None
    profile_stale: bool = False
    profile_skipped_reason: str | None = None
    profile_source_size: int | None = None
    profile_source_mtime_ns: int | None = None
    unavailable: bool = False


@dataclass(frozen=True, slots=True)
class CatalogBinding:
    entry_id: UUID
    alias: str
    path: Path
    source_format: SourceFormat


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    path: Path
    size: int | None
    mtime_ns: int | None


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    request_id: UUID
    engine: EngineKind
    source_dialect: str
    original_sql: str
    executable_sql: str
    catalog: tuple[CatalogBinding, ...]
    preview_limit: int
    submitted_at: datetime
    source_snapshots: tuple[SourceSnapshot, ...] = ()
    parameters: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class QueryResult:
    request_id: UUID
    status: ExecutionStatus
    frame: pl.DataFrame | None
    execution_seconds: float
    preview_row_count: int
    total_row_count: int | None
    truncated: bool
    completed_at: datetime
    error_type: str | None = None
    error_message: str | None = None
    error_detail: str | None = None

    def __post_init__(self):
        if self.status is ExecutionStatus.FAILED:
            if self.error_type is None:
                raise ValueError("failed QueryResult requires error_type")
            if self.error_message is None:
                raise ValueError("failed QueryResult requires error_message")
            if self.frame is not None:
                raise ValueError("failed QueryResult must not include a frame")
            return

        if self.status is ExecutionStatus.CANCELLED:
            if self.frame is not None:
                raise ValueError("cancelled QueryResult must not include a frame")
            return

        if self.frame is None:
            raise ValueError("successful QueryResult requires a frame")


@dataclass(frozen=True, slots=True)
class NumericSelectionStatistics:
    """Aggregates for a selection made entirely from numeric columns."""

    total: int | float | None
    mean: float | None
    minimum: int | float | None
    maximum: int | float | None


@dataclass(frozen=True, slots=True)
class SelectionStatistics:
    """Counts and optional numeric aggregates for multiple selected result cells."""

    cell_count: int
    distinct_count: int
    null_count: int
    numeric: NumericSelectionStatistics | None


@dataclass(frozen=True, slots=True)
class SchemaResult:
    entry_id: UUID
    columns: tuple[ColumnSchema, ...] | None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """Summary statistics returned for one dataset column."""

    name: str
    data_type: str
    min: str | None
    max: str | None
    approx_unique: int | None
    avg: str | None
    std: str | None
    q25: str | None
    q50: str | None
    q75: str | None
    count: int | None
    null_percentage: float | None


@dataclass(frozen=True, slots=True)
class ProfileResult:
    """Profiles for one catalog entry, or a normalized profiling error."""

    entry_id: UUID
    profiles: tuple[ColumnProfile, ...] | None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class SqlDiagnostic:
    message: str
    severity: str
    start_line: int
    start_column: int
    end_line: int | None = None
    end_column: int | None = None
