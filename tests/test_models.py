import subprocess
import sys
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

import polars as pl
import pytest

from wherewolf import execution
from wherewolf.domain import (
    ColumnProfile,
    CompletionKind,
    EngineKind,
    ExecutionStatus,
    ProfileResult,
    SourceFormat,
)
from wherewolf.domain import models as domain_models
from wherewolf.domain.errors import UnsupportedFormatError


def test_models():
    qr = execution.models.QueryResult()
    assert qr.success is True
    assert isinstance(qr.df, pl.DataFrame)


def test_domain_enums_are_str_enums() -> None:
    assert issubclass(EngineKind, StrEnum)
    assert issubclass(SourceFormat, StrEnum)
    assert issubclass(ExecutionStatus, StrEnum)
    assert issubclass(CompletionKind, StrEnum)


def test_domain_enum_members_exactly() -> None:
    assert [item.value for item in EngineKind] == ["duckdb", "spark"]
    assert [item.value for item in SourceFormat] == ["csv", "parquet", "json", "jsonl", "xlsx"]
    assert "xls" not in [item.value for item in SourceFormat]
    assert [item.value for item in ExecutionStatus] == [
        "idle",
        "running",
        "cancellation_requested",
        "succeeded",
        "cancelled",
        "failed",
    ]
    assert [item.value for item in CompletionKind] == [
        "table",
        "cte",
        "column",
        "function",
        "keyword",
        "snippet",
    ]


def test_source_format_from_path_is_case_insensitive() -> None:
    assert SourceFormat.from_path(Path("a.XLSX")) is SourceFormat.XLSX
    with pytest.raises(UnsupportedFormatError):
        SourceFormat.from_path(Path("a.xls"))


def test_domain_models_are_frozen() -> None:
    catalog_entry = domain_models.CatalogEntry(
        id=uuid4(),
        alias="dataset",
        path=Path("/tmp/data.csv"),
        source_format=SourceFormat.CSV,
    )
    catalog_binding = domain_models.CatalogBinding(
        entry_id=catalog_entry.id,
        alias=catalog_entry.alias,
        path=catalog_entry.path,
        source_format=catalog_entry.source_format,
    )
    execution_request = domain_models.ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(catalog_binding,),
        preview_limit=1000,
        submitted_at=datetime.now(UTC),
    )
    query_result = domain_models.QueryResult(
        request_id=execution_request.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame(),
        execution_seconds=0.0,
        preview_row_count=0,
        total_row_count=0,
        truncated=False,
        completed_at=datetime.now(UTC),
    )
    schema_result = domain_models.SchemaResult(entry_id=catalog_entry.id, columns=())
    diagnostic = domain_models.SqlDiagnostic(
        message="ok",
        severity="info",
        start_line=1,
        start_column=1,
    )

    with pytest.raises(FrozenInstanceError):
        catalog_entry.alias = "other"  # type: ignore
    with pytest.raises(FrozenInstanceError):
        catalog_binding.alias = "other"  # type: ignore
    with pytest.raises(FrozenInstanceError):
        execution_request.preview_limit = 10  # type: ignore
    with pytest.raises(FrozenInstanceError):
        query_result.total_row_count = 10  # type: ignore
    with pytest.raises(FrozenInstanceError):
        schema_result.columns = None  # type: ignore
    with pytest.raises(FrozenInstanceError):
        diagnostic.message = "bad"  # type: ignore


def test_domain_queryresult_distinct_from_execution_queryresult() -> None:
    assert domain_models.QueryResult is not execution.models.QueryResult


def test_column_profile_preserves_non_numeric_statistics_as_none() -> None:
    entry_id = uuid4()
    profile = ColumnProfile(
        name="category",
        data_type="VARCHAR",
        min="alpha",
        max="omega",
        approx_unique=3,
        avg=None,
        std=None,
        q25=None,
        q50=None,
        q75=None,
        count=4,
        null_percentage=25.0,
    )
    result = ProfileResult(entry_id=entry_id, profiles=(profile,))

    assert result.entry_id == entry_id
    assert result.error_type is None
    assert result.profiles is not None
    assert result.profiles[0].avg is None


def test_catalog_binding_copies_path_snapshot() -> None:
    entry_path = Path("/tmp/original.csv")
    entry = domain_models.CatalogEntry(
        id=uuid4(),
        alias="dataset",
        path=entry_path,
        source_format=SourceFormat.CSV,
    )
    binding = domain_models.CatalogBinding(
        entry_id=entry.id,
        alias=entry.alias,
        path=Path(entry.path),
        source_format=entry.source_format,
    )

    entry_path = Path("/tmp/changed.csv")
    assert binding.path != entry_path
    assert binding.path == Path("/tmp/original.csv")


def test_query_result_failure_requires_no_frame_and_error_fields() -> None:
    with pytest.raises(ValueError):
        domain_models.QueryResult(
            request_id=uuid4(),
            status=ExecutionStatus.FAILED,
            frame=pl.DataFrame(),
            execution_seconds=0.0,
            preview_row_count=0,
            total_row_count=0,
            truncated=False,
            completed_at=datetime.now(UTC),
            error_type="RuntimeError",
            error_message="boom",
        )
    with pytest.raises(ValueError):
        domain_models.QueryResult(
            request_id=uuid4(),
            status=ExecutionStatus.SUCCEEDED,
            frame=None,
            execution_seconds=0.0,
            preview_row_count=0,
            total_row_count=0,
            truncated=False,
            completed_at=datetime.now(UTC),
        )


def test_domain_models_import_has_no_runtime_heavy_modules() -> None:
    code = (
        "import sys\n"
        "import wherewolf.domain.models\n"
        "forbidden = ('PyQt6', 'duckdb', 'pyspark')\n"
        "missing = [name for name in forbidden if name in sys.modules]\n"
        "if missing:\n"
        "    raise SystemExit(f\"unexpected modules loaded: {', '.join(missing)}\")\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
