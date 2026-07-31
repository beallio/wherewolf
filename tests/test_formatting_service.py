from wherewolf.services import SqlFormattingService


def test_same_dialect_pretty_formats_without_mutating_input() -> None:
    service = SqlFormattingService()
    source = "select a,b from t where a=1"
    result = service.format_sql(source, dialect="duckdb")

    assert result.formatted_sql is not None
    assert result.formatted_sql.startswith("SELECT")
    assert "FROM t" in result.formatted_sql
    assert result.diagnostics == ()
    assert source == "select a,b from t where a=1"


def test_multiple_statements_are_all_retained() -> None:
    service = SqlFormattingService()
    source = "select 1; select 2; select 3;"
    result = service.format_sql(source, dialect="duckdb")

    assert result.formatted_sql is not None
    assert result.formatted_sql.count("SELECT") == 3
    assert not result.diagnostics


def test_trailing_semicolon_preserved_when_present_but_not_forced_when_absent() -> None:
    service = SqlFormattingService()

    with_semicolon = service.format_sql("select 1;", dialect="duckdb")
    without_semicolon = service.format_sql("select 1", dialect="duckdb")

    assert with_semicolon.formatted_sql is not None
    assert with_semicolon.formatted_sql.rstrip().endswith(";")
    assert without_semicolon.formatted_sql is not None
    assert not without_semicolon.formatted_sql.rstrip().endswith(";")


def test_line_endings_are_preserved() -> None:
    service = SqlFormattingService()
    source = "select 1;\r\nselect 2;\r\n"

    formatted = service.format_sql(source, dialect="duckdb")
    assert formatted.formatted_sql is not None
    assert "\r\n" in formatted.formatted_sql
    assert "\n" not in formatted.formatted_sql.replace("\r\n", "")


def test_comments_survive_formatting() -> None:
    service = SqlFormattingService()
    source = "-- before\nselect 1; /* mid */\n-- after\nselect 2;"

    formatted = service.format_sql(source, dialect="duckdb")
    assert formatted.formatted_sql is not None
    assert "before" in formatted.formatted_sql.lower()
    assert "mid" in formatted.formatted_sql.lower()
    assert "after" in formatted.formatted_sql.lower()


def test_quoted_identifier_quoting_is_preserved() -> None:
    service = SqlFormattingService()
    source = 'select "quoted;id" from "table";'

    formatted = service.format_sql(source, dialect="duckdb")
    assert formatted.formatted_sql is not None
    assert '"quoted;id"' in formatted.formatted_sql


def test_semicolon_inside_string_does_not_split_statement() -> None:
    service = SqlFormattingService()
    source = "select 'a;b;c' as value;"

    formatted = service.format_sql(source, dialect="duckdb")
    assert formatted.formatted_sql is not None
    assert formatted.formatted_sql.count(";") > 0
    assert "'a;b;c'" in formatted.formatted_sql


def test_dialect_is_preserved_for_duckdb_and_spark() -> None:
    service = SqlFormattingService()
    duck = service.format_sql("select * from read_csv_auto('a.csv')", dialect="duckdb")
    spark = service.format_sql("select explode(array(1,2,3))", dialect="spark")

    assert duck.formatted_sql is not None
    assert spark.formatted_sql is not None
    assert "READ_CSV_AUTO" in duck.formatted_sql
    assert "EXPLODE" in spark.formatted_sql


def test_parse_error_returns_original_and_diagnostic() -> None:
    service = SqlFormattingService()
    source = "select from"
    result = service.format_sql(source, dialect="duckdb")

    assert result.formatted_sql == source
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].severity == "error"
