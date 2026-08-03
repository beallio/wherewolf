from wherewolf.services.identifier_quoting import quote_identifier


def test_quote_identifier_plain_lowercase() -> None:
    assert quote_identifier("column_name") == "column_name"
    assert quote_identifier("col1") == "col1"
    assert quote_identifier("_private") == "_private"


def test_quote_identifier_mixed_case() -> None:
    assert quote_identifier("ColName") == '"ColName"'
    assert quote_identifier("UPPERCASE") == '"UPPERCASE"'


def test_quote_identifier_with_spaces() -> None:
    assert quote_identifier("first name") == '"first name"'


def test_quote_identifier_leading_digit() -> None:
    assert quote_identifier("123col") == '"123col"'


def test_quote_identifier_reserved_word() -> None:
    assert quote_identifier("select") == '"select"'
    assert quote_identifier("WHERE") == '"WHERE"'
    assert quote_identifier("order") == '"order"'


def test_quote_identifier_embedded_quotes() -> None:
    # Stated rule: embedded double quotes are escaped by doubling them ("")
    assert quote_identifier('col"name') == '"col""name"'
    assert quote_identifier('a"b"c') == '"a""b""c"'
