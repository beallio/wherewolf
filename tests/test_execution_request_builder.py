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
    from wherewolf.domain import CatalogBinding

    assert isinstance(request.catalog[0], CatalogBinding)
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


def test_build_same_dialect_does_not_rewrite_sql():
    catalog_service = CatalogService()
    sql = "SELECT 1 AS col"
    req = ExecutionRequestBuilder.build(
        sql=sql,
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=catalog_service,
    )
    assert req.original_sql == sql
    assert req.executable_sql == sql


def test_build_different_dialect_translates_sql():
    catalog_service = CatalogService()
    # T-SQL top N -> DuckDB LIMIT
    tsql = "SELECT TOP 10 * FROM tbl"
    req = ExecutionRequestBuilder.build(
        sql=tsql,
        source_dialect="tsql",
        engine=EngineKind.DUCKDB,
        catalog_service=catalog_service,
    )
    assert req.original_sql == tsql
    assert "LIMIT 10" in req.executable_sql


@pytest.mark.parametrize(
    ("source_dialect", "sql", "expected_by_engine"),
    (
        (
            "oracle",
            "SELECT NVL(name, 'x') FROM emp",
            {EngineKind.DUCKDB: "COALESCE(name, 'x')", EngineKind.SPARK: "COALESCE(name, 'x')"},
        ),
        (
            "postgres",
            "SELECT id::text FROM t",
            {EngineKind.DUCKDB: "CAST(id AS TEXT)", EngineKind.SPARK: "CAST(id AS STRING)"},
        ),
    ),
)
def test_build_oracle_and_postgres_sql_transpiles_for_each_execution_engine(
    source_dialect: str, sql: str, expected_by_engine: dict[EngineKind, str]
) -> None:
    catalog_service = CatalogService()

    for engine, expected_sql in expected_by_engine.items():
        request = ExecutionRequestBuilder.build(
            sql=sql,
            source_dialect=source_dialect,
            engine=engine,
            catalog_service=catalog_service,
        )

        assert request.executable_sql != request.original_sql
        assert expected_sql in request.executable_sql


def test_build_multi_statement_preserves_all_statements():
    catalog_service = CatalogService()
    sql = "SELECT 1; SELECT 2"
    req = ExecutionRequestBuilder.build(
        sql=sql,
        source_dialect="tsql",
        engine=EngineKind.DUCKDB,
        catalog_service=catalog_service,
    )
    assert req.original_sql == sql
    # Multi-statement preserved in executable_sql (both statements present)
    assert "1" in req.executable_sql
    assert "2" in req.executable_sql


def test_build_untranslatable_sql_raises_translation_error():
    from wherewolf.domain.errors import TranslationError

    catalog_service = CatalogService()
    sql = "INVALID SYNTAX (((("
    with pytest.raises(TranslationError):
        ExecutionRequestBuilder.build(
            sql=sql,
            source_dialect="tsql",
            engine=EngineKind.DUCKDB,
            catalog_service=catalog_service,
        )
