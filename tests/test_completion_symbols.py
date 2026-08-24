from wherewolf.services.completion_symbols import AliasCategory, collect_symbols


def test_collect_symbols_finds_from_and_join_aliases_with_or_without_as() -> None:
    sql = "SELECT o.id, c.name FROM monthly_sales AS o JOIN customers c ON o.customer_id = c.id"

    symbols = collect_symbols(sql, len(sql), "duckdb")

    assert [(symbol.name, symbol.relation) for symbol in symbols.table_aliases] == [
        ("o", "monthly_sales"),
        ("c", "customers"),
    ]


def test_collect_symbols_can_find_table_alias_after_cursor_in_select_list() -> None:
    sql = "SELECT o FROM monthly_sales AS o"

    symbols = collect_symbols(sql, len("SELECT o"), "duckdb")

    assert [(symbol.name, symbol.relation) for symbol in symbols.table_aliases] == [
        ("o", "monthly_sales")
    ]


def test_collect_symbols_uses_lexical_fallback_for_incomplete_statement() -> None:
    sql = "SELECT o. FROM monthly_sales o WHERE ("

    symbols = collect_symbols(sql, len(sql), "duckdb")

    assert [(symbol.name, symbol.relation) for symbol in symbols.table_aliases] == [
        ("o", "monthly_sales")
    ]


def test_collect_symbols_classifies_postfix_and_prefix_select_aliases() -> None:
    sql = """
        SELECT price * quantity AS revenue_total,
               gross: SUM(amount),
               ROW_NUMBER() OVER () AS row_rank
        FROM monthly_sales
        ORDER BY revenue_total
    """

    symbols = collect_symbols(sql, len(sql), "duckdb")

    assert [(symbol.name, symbol.category) for symbol in symbols.expression_aliases] == [
        ("revenue_total", AliasCategory.NON_AGGREGATE),
        ("gross", AliasCategory.AGGREGATE),
        ("row_rank", AliasCategory.WINDOW),
    ]


def test_collect_symbols_isolates_statement_and_nested_scope() -> None:
    multi_statement_sql = "SELECT * FROM old_table old; SELECT * FROM current_table cur WHERE "
    multi_symbols = collect_symbols(multi_statement_sql, len(multi_statement_sql), "duckdb")
    assert [(symbol.name, symbol.relation) for symbol in multi_symbols.table_aliases] == [
        ("cur", "current_table")
    ]

    nested_sql = "SELECT * FROM outer_table o WHERE EXISTS (SELECT * FROM inner_table i WHERE )"
    nested_symbols = collect_symbols(nested_sql, len(nested_sql) - 1, "duckdb")
    assert [(symbol.name, symbol.relation) for symbol in nested_symbols.table_aliases] == [
        ("i", "inner_table")
    ]


def test_collect_symbols_excludes_later_select_aliases() -> None:
    sql = "SELECT amount AS earlier, price AS later_alias FROM monthly_sales"
    cursor_offset = sql.index(", price")

    symbols = collect_symbols(sql, cursor_offset, "duckdb")

    assert [symbol.name for symbol in symbols.expression_aliases] == ["earlier"]


def test_collect_symbols_matches_cte_and_outer_select_scopes_by_source_position() -> None:
    sql = """WITH cte AS (
        SELECT source_id AS cte_alias FROM source_table s WHERE source_id > 0
    )
    SELECT outer_id AS outer_alias FROM outer_table o ORDER BY outer_alias"""

    inner_symbols = collect_symbols(sql, sql.index("WHERE ") + len("WHERE "), "duckdb")
    outer_symbols = collect_symbols(sql, len(sql), "duckdb")

    assert [(symbol.name, symbol.relation) for symbol in inner_symbols.table_aliases] == [
        ("s", "source_table")
    ]
    assert [symbol.name for symbol in inner_symbols.expression_aliases] == ["cte_alias"]
    assert [(symbol.name, symbol.relation) for symbol in outer_symbols.table_aliases] == [
        ("o", "outer_table")
    ]
    assert [symbol.name for symbol in outer_symbols.expression_aliases] == ["outer_alias"]
