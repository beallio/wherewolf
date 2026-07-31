from wherewolf.services import StatementService


def test_split_single_statement() -> None:
    service = StatementService()
    result = service.split_statements("SELECT 1;")

    assert len(result) == 1
    assert result[0].text == "SELECT 1;"
    assert result[0].start_offset == 0
    assert result[0].end_offset == 9


def test_find_statement_selects_cursor_within_statement() -> None:
    service = StatementService()
    sql = "SELECT 1;\nSELECT 2;\nSELECT 3"

    first = service.find_statement(sql, 2)
    second = service.find_statement(sql, 12)
    third = service.find_statement(sql, 22)

    assert first.text == "SELECT 1;"
    assert second.text == "SELECT 2;"
    assert third.text == "SELECT 3"
    assert first.start_offset == 0
    assert second.start_offset > first.start_offset
    assert third.start_offset > second.start_offset


def test_split_ignores_semicolon_inside_single_quotes() -> None:
    service = StatementService()
    sql = "SELECT 'a;b;c' AS value;"
    result = service.split_statements(sql)

    assert len(result) == 1
    assert result[0].text == "SELECT 'a;b;c' AS value;"


def test_split_ignores_semicolon_inside_double_quotes() -> None:
    service = StatementService()
    sql = 'SELECT "a;b;c" AS value;'
    result = service.split_statements(sql)

    assert len(result) == 1
    assert result[0].text == 'SELECT "a;b;c" AS value;'


def test_split_ignores_semicolon_inside_line_comment() -> None:
    service = StatementService()
    sql = "SELECT 1 -- first; ignored\n;\nSELECT 2;"

    result = service.split_statements(sql)

    assert len(result) == 2
    assert result[0].text == "SELECT 1"
    assert result[1].text == "SELECT 2;"


def test_split_ignores_semicolon_inside_block_comment() -> None:
    service = StatementService()
    sql = "SELECT 1 /* c; comment */; SELECT 2;"

    result = service.split_statements(sql)

    assert len(result) == 2
    assert result[0].text == "SELECT 1 /* c; comment */;"
    assert result[1].text == "SELECT 2;"


def test_escaped_quote_does_not_end_string() -> None:
    service = StatementService()
    sql = "SELECT 'a\\'b;c' AS value; SELECT 2;"

    result = service.split_statements(sql)

    assert len(result) == 2
    assert result[0].text == "SELECT 'a\\'b;c' AS value;"


def test_trailing_semicolon_is_preserved() -> None:
    service = StatementService()
    statement = service.find_statement("SELECT 1;\n", 4)

    assert statement.text == "SELECT 1;"
    assert statement.end_offset == 9


def test_crlf_and_lf_offsets_are_preserved() -> None:
    service = StatementService()
    sql = "SELECT 1;\r\nSELECT 2;\nSELECT 3;"

    statements = service.split_statements(sql)
    assert statements[0].start_offset == 0
    assert statements[1].start_offset == 11
    assert statements[2].start_offset == 21

    lf = service.find_statement(sql, 12)
    assert lf.text == "SELECT 2;"


def test_whitespace_only_document_has_no_statement() -> None:
    service = StatementService()
    assert service.find_statement("   \n\t", 0).text is None


def test_find_statement_returns_reason_when_ambiguous() -> None:
    service = StatementService()
    assert (
        service.find_statement("SELECT 1; SELECT 2;", 9).reason
        == "no unambiguous statement for this cursor position"
    )
