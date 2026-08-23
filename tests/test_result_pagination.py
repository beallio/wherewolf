import pytest

from wherewolf.services.result_pagination import build_page_sql, has_top_level_order_by


def test_build_page_sql_wraps_one_query_with_parameterized_limit_and_offset() -> None:
    page_sql = build_page_sql("SELECT * FROM rows")

    assert page_sql.startswith("SELECT * FROM (SELECT * FROM rows) AS ")
    assert page_sql.endswith(" LIMIT ? OFFSET ?")


def test_build_page_sql_removes_only_the_final_terminator_and_trailing_comment() -> None:
    page_sql = build_page_sql(" \nSELECT 'literal;value' AS value /* comment;value */; -- done\n")

    assert "literal;value" in page_sql
    assert "comment;value" in page_sql
    assert "-- done" not in page_sql
    assert "*/;)" not in page_sql


@pytest.mark.parametrize("sql", ("", " \n\t ", "SELECT 1; SELECT 2"))
def test_build_page_sql_rejects_empty_or_multi_statement_sql(sql: str) -> None:
    with pytest.raises(ValueError):
        build_page_sql(sql)


@pytest.mark.parametrize(
    "sql",
    (
        "SELECT * FROM rows ORDER BY id",
        "WITH selected AS (SELECT * FROM rows) SELECT * FROM selected ORDER BY id",
    ),
)
def test_has_top_level_order_by_recognizes_final_query_order(sql: str) -> None:
    assert has_top_level_order_by(sql) is True


@pytest.mark.parametrize(
    "sql",
    (
        "WITH selected AS (SELECT * FROM rows ORDER BY id) SELECT * FROM selected",
        "SELECT * FROM (SELECT * FROM rows ORDER BY id) AS selected",
        "SELECT row_number() OVER (ORDER BY id) FROM rows",
    ),
)
def test_has_top_level_order_by_ignores_nested_ordering(sql: str) -> None:
    assert has_top_level_order_by(sql) is False


@pytest.mark.parametrize(
    "sql",
    (
        "SELECT * FROM rows ORDER BY category",
        "SELECT * FROM rows ORDER BY random()",
    ),
)
def test_has_top_level_order_by_is_syntactic_not_a_determinism_guarantee(sql: str) -> None:
    assert has_top_level_order_by(sql) is True


def test_has_top_level_order_by_fails_closed_to_the_warning_when_sql_cannot_be_parsed() -> None:
    assert has_top_level_order_by("SELECT * FROM )") is False


def test_build_page_sql_preserves_inner_limit_and_offset_semantics() -> None:
    page_sql = build_page_sql("SELECT * FROM rows ORDER BY id LIMIT 10 OFFSET 5")

    assert "ORDER BY id LIMIT 10 OFFSET 5" in page_sql
    assert page_sql.endswith(" LIMIT ? OFFSET ?")
