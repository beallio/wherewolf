from wherewolf.services.query_parameters import (
    bind_dataset_tokens,
    bind_parameters,
    contains_dataset_token,
    extract_parameters,
)


def test_extract_parameters_ignores_casts_literals_and_comments() -> None:
    sql = """
        SELECT value::int, ':not_a_parameter', ":also_not_a_parameter"
        FROM data -- :line_comment
        /* :block_comment */
        WHERE a = :first AND b = :second AND c = :first
    """

    assert extract_parameters(sql) == ("first", "second")


def test_extract_parameters_returns_no_cast_parameter() -> None:
    assert extract_parameters("SELECT a::int FROM data") == ()


def test_bind_parameters_uses_scanner_spans_without_interpolating_values() -> None:
    injection = "'; DROP TABLE t; --"
    sql, values = bind_parameters(
        "SELECT :value, ':value', amount::int -- :value\nWHERE name = :value",
        {"value": injection},
    )

    assert sql == "SELECT ?, ':value', amount::int -- :value\nWHERE name = ?"
    assert values == [injection, injection]


def test_dataset_token_binding_changes_only_real_code_tokens() -> None:
    sql = """SELECT * FROM {dataset} JOIN {dataset} AS other ON true
WHERE literal = '{dataset}' AND identifier = "{dataset}"
-- {dataset}
/* {dataset} */
AND escaped = 'it''s {dataset}'"""

    assert contains_dataset_token(sql)
    assert (
        bind_dataset_tokens(sql, '"weekly export"')
        == """SELECT * FROM "weekly export" JOIN "weekly export" AS other ON true
WHERE literal = '{dataset}' AND identifier = "{dataset}"
-- {dataset}
/* {dataset} */
AND escaped = 'it''s {dataset}'"""
    )
    assert not contains_dataset_token(
        "SELECT '{dataset}', \"{dataset}\" -- {dataset}\n/* {dataset} */"
    )
