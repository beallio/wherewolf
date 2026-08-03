import pytest

from wherewolf.domain.errors import TranslationError
from wherewolf.translation import Translator


def test_translate_duckdb_to_spark() -> None:
    translator = Translator()
    # DuckDB specific: list comprehension, or different limit syntax
    duckdb_sql = "SELECT * FROM dataset LIMIT 10"
    spark_sql = translator.translate(duckdb_sql, from_dialect="duckdb", to_dialect="spark")

    assert "SELECT" in spark_sql.upper()
    assert "LIMIT 10" in spark_sql.upper() or "TOP 10" in spark_sql.upper()


def test_translate_spark_to_duckdb() -> None:
    translator = Translator()
    spark_sql = "SELECT * FROM dataset LIMIT 10"
    duckdb_sql = translator.translate(spark_sql, from_dialect="spark", to_dialect="duckdb")

    assert "SELECT" in duckdb_sql.upper()
    assert "LIMIT 10" in duckdb_sql.upper()


def test_translate_to_tsql() -> None:
    translator = Translator()
    duckdb_sql = "SELECT * FROM dataset LIMIT 10"
    tsql_sql = translator.translate(duckdb_sql, from_dialect="duckdb", to_dialect="tsql")

    assert "SELECT" in tsql_sql.upper()
    assert "TOP 10" in tsql_sql.upper()


def test_invalid_dialect() -> None:
    translator = Translator()
    with pytest.raises(ValueError):
        translator.translate("SELECT 1", from_dialect="invalid", to_dialect="spark")


def test_translate_statements_preserves_multiple_statements() -> None:
    translator = Translator()
    translated = translator.translate_statements(
        "SELECT 1; SELECT 2", from_dialect="duckdb", to_dialect="spark"
    )

    assert isinstance(translated, tuple)
    assert len(translated) == 2


def test_translate_statements_single_statement_returns_one() -> None:
    translator = Translator()
    translated = translator.translate_statements(
        "SELECT 1", from_dialect="duckdb", to_dialect="spark"
    )

    assert isinstance(translated, tuple)
    assert len(translated) == 1


def test_translate_statements_empty_query_returns_empty_tuple() -> None:
    translator = Translator()
    assert (
        translator.translate_statements("   \n\t", from_dialect="duckdb", to_dialect="spark") == ()
    )


def test_translate_statements_bad_dialect_fails() -> None:
    translator = Translator()
    with pytest.raises(ValueError):
        translator.translate_statements("SELECT 1", from_dialect="invalid", to_dialect="spark")


def test_translate_statements_unparseable_query_raises_translation_error() -> None:
    translator = Translator()
    with pytest.raises(TranslationError) as exc:
        translator.translate_statements("SELECT FROM", from_dialect="duckdb", to_dialect="spark")
    assert "SELECT FROM" in str(exc.value)


def test_translate_still_only_returns_first_statement() -> None:
    translator = Translator()
    result = translator.translate("SELECT 1; SELECT 2", from_dialect="duckdb", to_dialect="spark")

    assert (
        result
        == translator.translate_statements("SELECT 1", from_dialect="duckdb", to_dialect="spark")[0]
    )
