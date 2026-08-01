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


def test_cte_suggested_in_from_clause() -> None:
    catalog = (_make_catalog_entry("orders"),)
    service = SqlCompletionService()

    sql = "WITH recent AS (SELECT * FROM orders)\nSELECT * FROM "
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    cte_items = [item for item in items if item.kind == CompletionKind.CTE]
    assert len(cte_items) == 1
    assert cte_items[0].label == "recent"


def test_cte_shadows_catalog_alias() -> None:
    catalog = (_make_catalog_entry("orders"),)
    service = SqlCompletionService()

    sql = "WITH orders AS (SELECT 1 AS x)\nSELECT * FROM "
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    table_names = [item.label for item in items if item.label == "orders"]
    assert len(table_names) == 1
    assert items[0].kind == CompletionKind.CTE


def test_cte_qualified_columns_derivable() -> None:
    orders_cols = (ColumnSchema("id", "INTEGER"), ColumnSchema("amount", "DOUBLE"))
    catalog = (_make_catalog_entry("orders", orders_cols),)
    service = SqlCompletionService()

    sql = "WITH recent AS (SELECT * FROM orders)\nSELECT recent."
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.COLUMN]
    assert "id" in labels
    assert "amount" in labels


def test_cte_qualified_columns_not_derivable_returns_nothing() -> None:
    service = SqlCompletionService()
    sql = "WITH unknown AS (SELECT UNKNOWN_FUNC())\nSELECT unknown."
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=())

    items = service.complete(ctx)
    column_items = [item for item in items if item.kind == CompletionKind.COLUMN]
    assert len(column_items) == 0


def test_completion_ranking_order() -> None:
    service = SqlCompletionService()
    catalog = (_make_catalog_entry("customer_table", (ColumnSchema("customer_id", "INT"),)),)
    sql = "WITH cnt AS (SELECT 1 AS n)\nSELECT c FROM customer_table"
    # cursor after "SELECT c"
    cursor_offset = sql.find("SELECT c") + 8
    ctx = CompletionContext(sql=sql, cursor_offset=cursor_offset, dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    matching_kinds = [item.kind for item in items if item.label.lower().startswith("c")]

    # Expected order: CTE, TABLE, COLUMN, FUNCTION, KEYWORD
    # e.g., cnt (CTE), customer_table (TABLE), customer_id (COLUMN), COUNT/COALESCE (FUNCTION), CAST/CASE (KEYWORD)
    cte_idx = matching_kinds.index(CompletionKind.CTE)
    tbl_idx = matching_kinds.index(CompletionKind.TABLE)
    col_idx = matching_kinds.index(CompletionKind.COLUMN)
    fn_idx = matching_kinds.index(CompletionKind.FUNCTION)
    kw_idx = matching_kinds.index(CompletionKind.KEYWORD)

    assert cte_idx < tbl_idx < col_idx < fn_idx < kw_idx


def test_identifier_quoting_and_function_parens() -> None:
    service = SqlCompletionService()
    catalog = (
        _make_catalog_entry(
            "orders",
            (
                ColumnSchema("my col", "VARCHAR"),
                ColumnSchema("select", "INTEGER"),
            ),
        ),
    )

    sql = "SELECT o. FROM orders o"
    ctx = CompletionContext(sql=sql, cursor_offset=9, dialect="duckdb", catalog=catalog)
    items = service.complete(ctx)

    item_dict = {item.label: item for item in items}
    assert item_dict["my col"].insert_text == '"my col"'
    assert item_dict["select"].insert_text == '"select"'

    sql_fn = "SELECT COAL"
    ctx_fn = CompletionContext(
        sql=sql_fn, cursor_offset=len(sql_fn), dialect="duckdb", catalog=catalog
    )
    fn_items = service.complete(ctx_fn)
    coalesce_item = next(item for item in fn_items if item.label == "COALESCE")

    assert coalesce_item.kind == CompletionKind.FUNCTION
    assert coalesce_item.insert_text == "COALESCE("


def test_ranking_determinism() -> None:
    service = SqlCompletionService()
    catalog = (
        _make_catalog_entry("b_tbl"),
        _make_catalog_entry("a_tbl"),
    )
    sql = "SELECT * FROM "
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=catalog)

    items = service.complete(ctx)
    labels = [item.label for item in items if item.kind == CompletionKind.TABLE]
    assert labels == ["a_tbl", "b_tbl"]


def test_call_tip_known_function() -> None:
    service = SqlCompletionService()
    sql = "SELECT COALESCE("
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=())
    tip = service.call_tip(ctx)
    assert tip is not None
    assert "COALESCE(" in tip


def test_call_tip_nested_function_returns_innermost() -> None:
    service = SqlCompletionService()
    sql = "SELECT COALESCE(COUNT("
    ctx = CompletionContext(sql=sql, cursor_offset=len(sql), dialect="duckdb", catalog=())
    tip = service.call_tip(ctx)
    assert tip is not None
    assert "COUNT(" in tip


def test_call_tip_outside_or_unknown_returns_none() -> None:
    service = SqlCompletionService()
    sql_outside = "SELECT * FROM orders"
    ctx_outside = CompletionContext(
        sql=sql_outside, cursor_offset=len(sql_outside), dialect="duckdb", catalog=()
    )
    assert service.call_tip(ctx_outside) is None

    sql_unknown = "SELECT UNKNOWN_FUNCTION("
    ctx_unknown = CompletionContext(
        sql=sql_unknown, cursor_offset=len(sql_unknown), dialect="duckdb", catalog=()
    )
    assert service.call_tip(ctx_unknown) is None


def test_call_tip_inside_string_or_comment_returns_none() -> None:
    service = SqlCompletionService()
    sql_str = "SELECT 'COALESCE('"
    ctx_str = CompletionContext(sql=sql_str, cursor_offset=17, dialect="duckdb", catalog=())
    assert service.call_tip(ctx_str) is None

    sql_cmt = "SELECT -- COALESCE("
    ctx_cmt = CompletionContext(sql=sql_cmt, cursor_offset=18, dialect="duckdb", catalog=())
    assert service.call_tip(ctx_cmt) is None
