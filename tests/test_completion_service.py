from pathlib import Path
from uuid import uuid4

from wherewolf.domain.enums import CompletionKind, SourceFormat
from wherewolf.domain.models import CatalogEntry, CompletionContext
from wherewolf.services.completion_service import SqlCompletionService


def _make_catalog_entry(alias: str) -> CatalogEntry:
    return CatalogEntry(
        id=uuid4(),
        alias=alias,
        path=Path(f"/tmp/{alias}.csv"),
        source_format=SourceFormat.CSV,
        schema=(),
    )


def test_complete_from_suggests_catalog_aliases() -> None:
    service = SqlCompletionService()
    catalog = (_make_catalog_entry("orders"), _make_catalog_entry("customers"))

    sql = "SELECT *\nFROM "
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.TABLE]
    assert "orders" in labels
    assert "customers" in labels


def test_complete_from_prefix_filtering_case_insensitive() -> None:
    service = SqlCompletionService()
    catalog = (_make_catalog_entry("orders"), _make_catalog_entry("customers"))

    sql = "SELECT *\nFROM ord"
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.TABLE]
    assert labels == ["orders"]


def test_complete_empty_catalog_no_table_suggestions() -> None:
    service = SqlCompletionService()
    sql = "SELECT *\nFROM "
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=())

    items = service.complete(ctx)
    table_items = [item for item in items if item.kind == CompletionKind.TABLE]
    assert len(table_items) == 0


def test_complete_suppressed_context_returns_empty() -> None:
    service = SqlCompletionService()
    catalog = (_make_catalog_entry("orders"),)
    sql = "SELECT 'FROM orders'"
    ctx = CompletionContext(sql=sql, cursor_offset=12, dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    assert len(items) == 0
