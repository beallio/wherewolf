from pathlib import Path
from uuid import uuid4

import pytest

from wherewolf.domain.enums import CompletionKind, SourceFormat
from wherewolf.domain.models import CatalogEntry, ColumnSchema, CompletionContext
from wherewolf.services.completion_service import SqlCompletionService


def _make_catalog_entry(alias: str, schema: tuple[ColumnSchema, ...] | None = ()) -> CatalogEntry:
    return CatalogEntry(
        id=uuid4(),
        alias=alias,
        path=Path(f"/tmp/{alias}.csv"),
        source_format=SourceFormat.CSV,
        schema=schema,
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


def test_qualified_alias_returns_only_target_table_columns() -> None:
    orders_cols = (ColumnSchema("order_id", "INTEGER"), ColumnSchema("total", "DOUBLE"))
    cust_cols = (ColumnSchema("customer_id", "INTEGER"), ColumnSchema("name", "VARCHAR"))
    catalog = (
        _make_catalog_entry("orders", orders_cols),
        _make_catalog_entry("customers", cust_cols),
    )
    service = SqlCompletionService()

    sql = "SELECT o. FROM orders AS o"
    ctx = CompletionContext(sql=sql, cursor_offset=9, dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.COLUMN]
    assert labels == ["order_id", "total"]


def test_join_qualified_alias_prioritises_joined_table_columns() -> None:
    orders_cols = (ColumnSchema("order_id", "INTEGER"), ColumnSchema("customer_id", "INTEGER"))
    cust_cols = (ColumnSchema("customer_id", "INTEGER"), ColumnSchema("email", "VARCHAR"))
    catalog = (
        _make_catalog_entry("orders", orders_cols),
        _make_catalog_entry("customers", cust_cols),
    )
    service = SqlCompletionService()

    sql = "SELECT * FROM orders o JOIN customers c ON o.customer_id = c."
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.COLUMN]
    assert labels == ["customer_id", "email"]


def test_qualified_bare_table_name() -> None:
    orders_cols = (ColumnSchema("order_id", "INTEGER"), ColumnSchema("total", "DOUBLE"))
    catalog = (_make_catalog_entry("orders", orders_cols),)
    service = SqlCompletionService()

    sql = "SELECT orders. FROM orders"
    ctx = CompletionContext(sql=sql, cursor_offset=14, dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.COLUMN]
    assert labels == ["order_id", "total"]


def test_qualified_unknown_alias_returns_no_columns() -> None:
    orders_cols = (ColumnSchema("order_id", "INTEGER"),)
    catalog = (_make_catalog_entry("orders", orders_cols),)
    service = SqlCompletionService()

    sql = "SELECT x. FROM orders o"
    ctx = CompletionContext(sql=sql, cursor_offset=9, dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.COLUMN]
    assert len(labels) == 0


def test_qualified_schema_none_does_not_raise_or_block() -> None:
    catalog = (_make_catalog_entry("orders", schema=None),)
    service = SqlCompletionService()

    sql = "SELECT o. FROM orders o"
    ctx = CompletionContext(sql=sql, cursor_offset=9, dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    assert len(items) == 0


def test_qualified_schema_empty_tuple_treated_as_no_columns() -> None:
    catalog = (_make_catalog_entry("orders", schema=()),)
    service = SqlCompletionService()

    sql = "SELECT o. FROM orders o"
    ctx = CompletionContext(sql=sql, cursor_offset=9, dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    assert len(items) == 0


@pytest.mark.parametrize(
    "sql,cursor_offset",
    [
        ("SELECT o. FROM orders o", 9),
        ("SELECT o. FROM orders o WHERE x =", 9),
        ("SELECT o.id FROM orders o BROKEN SYNTAX", 11),
    ],
)
def test_qualified_column_parseable_and_broken_sql(sql: str, cursor_offset: int) -> None:
    orders_cols = (ColumnSchema("id", "INTEGER"), ColumnSchema("amount", "DOUBLE"))
    catalog = (_make_catalog_entry("orders", orders_cols),)
    service = SqlCompletionService()

    ctx = CompletionContext(sql=sql, cursor_offset=cursor_offset, dialect="duckdb", catalog=catalog)
    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.COLUMN]
    assert "id" in labels
