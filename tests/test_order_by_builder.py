from wherewolf.services.order_by_builder import build_order_by_sql


def test_build_order_by_sql_simple_query_asc() -> None:
    sql = "SELECT * FROM users"
    result = build_order_by_sql(sql, "id", direction="ASC")
    assert result == "SELECT * FROM users ORDER BY id ASC"


def test_build_order_by_sql_simple_query_desc_quoted() -> None:
    sql = "SELECT * FROM users"
    result = build_order_by_sql(sql, "first name", direction="DESC")
    assert result == 'SELECT * FROM users ORDER BY "first name" DESC'


def test_build_order_by_sql_existing_order_by_wraps() -> None:
    # Stated rule: existing ORDER BY wraps as a subquery to preserve semantics
    sql = "SELECT * FROM users ORDER BY age ASC"
    result = build_order_by_sql(sql, "name", direction="ASC")
    assert (
        result
        == "SELECT * FROM (SELECT * FROM users ORDER BY age ASC) AS _subquery ORDER BY name ASC"
    )


def test_build_order_by_sql_existing_limit_wraps() -> None:
    # Stated rule: existing LIMIT wraps as a subquery so limit applies before reordering subquery
    sql = "SELECT * FROM users LIMIT 10"
    result = build_order_by_sql(sql, "id", direction="DESC")
    assert result == "SELECT * FROM (SELECT * FROM users LIMIT 10) AS _subquery ORDER BY id DESC"


def test_build_order_by_sql_reserved_word_column() -> None:
    sql = "SELECT * FROM items"
    result = build_order_by_sql(sql, "select", direction="ASC")
    assert result == 'SELECT * FROM items ORDER BY "select" ASC'
