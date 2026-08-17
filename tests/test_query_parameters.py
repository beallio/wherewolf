from wherewolf.services.query_parameters import extract_parameters


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
