from pathlib import Path
from uuid import uuid4

import pytest

from wherewolf.domain.enums import EngineKind, SourceFormat
from wherewolf.domain.models import CatalogEntry
from wherewolf.services.catalog_service import CatalogService
from wherewolf.services.execution_request_builder import ExecutionRequestBuilder


def test_build_execution_request_captures_snapshot():
    entry = CatalogEntry(
        id=uuid4(),
        alias="events",
        path=Path("/tmp/events.csv"),
        source_format=SourceFormat.CSV,
    )

    catalog_service = CatalogService(initial_entries=(entry,))
    sql = "SELECT * FROM events"

    request = ExecutionRequestBuilder.build(
        sql=sql,
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=catalog_service,
        preview_limit=500,
    )

    assert request.original_sql == "SELECT * FROM events"
    assert request.executable_sql == "SELECT * FROM events"
    assert request.source_dialect == "duckdb"
    assert request.engine == EngineKind.DUCKDB
    assert request.preview_limit == 500
    assert len(request.catalog) == 1
    assert request.catalog[0].alias == "events"

    # submitted_at is timezone-aware
    assert request.submitted_at.tzinfo is not None

    # Mutating catalog_service after build does not mutate request.catalog
    new_entry_path = Path("/tmp/other.parquet")
    catalog_service.add_paths((new_entry_path,))
    assert len(request.catalog) == 1
    assert len(catalog_service.entries) == 2

    # Editing local SQL variable or string does not mutate request
    sql_mutated = sql + " WHERE 1=1"
    assert request.original_sql == "SELECT * FROM events"
    assert sql_mutated != request.original_sql


def test_different_builds_have_unique_ids():
    catalog_service = CatalogService()
    req1 = ExecutionRequestBuilder.build(
        sql="SELECT 1",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=catalog_service,
    )
    req2 = ExecutionRequestBuilder.build(
        sql="SELECT 1",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=catalog_service,
    )

    assert req1.request_id != req2.request_id


def test_empty_or_whitespace_sql_rejected():
    catalog_service = CatalogService()

    with pytest.raises(ValueError, match="empty|whitespace"):
        ExecutionRequestBuilder.build(
            sql="",
            source_dialect="duckdb",
            engine=EngineKind.DUCKDB,
            catalog_service=catalog_service,
        )

    with pytest.raises(ValueError, match="empty|whitespace"):
        ExecutionRequestBuilder.build(
            sql="   \n\t  ",
            source_dialect="duckdb",
            engine=EngineKind.DUCKDB,
            catalog_service=catalog_service,
        )
