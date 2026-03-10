import pytest
from wherewolf.translation import Translator


def test_translate_duckdb_to_spark():
    translator = Translator()
    # DuckDB specific: list comprehension, or different limit syntax
    duckdb_sql = "SELECT * FROM dataset LIMIT 10"
    spark_sql = translator.translate(duckdb_sql, from_dialect="duckdb", to_dialect="spark")

    assert "SELECT" in spark_sql.upper()
    assert "LIMIT 10" in spark_sql.upper() or "TOP 10" in spark_sql.upper()


def test_translate_spark_to_duckdb():
    translator = Translator()
    spark_sql = "SELECT * FROM dataset LIMIT 10"
    duckdb_sql = translator.translate(spark_sql, from_dialect="spark", to_dialect="duckdb")

    assert "SELECT" in duckdb_sql.upper()
    assert "LIMIT 10" in duckdb_sql.upper()


def test_translate_to_tsql():
    translator = Translator()
    duckdb_sql = "SELECT * FROM dataset LIMIT 10"
    # T-SQL uses TOP for limits
    tsql_sql = translator.translate(duckdb_sql, from_dialect="duckdb", to_dialect="tsql")

    assert "SELECT" in tsql_sql.upper()
    assert "TOP 10" in tsql_sql.upper()


def test_invalid_dialect():
    translator = Translator()
    with pytest.raises(ValueError):
        translator.translate("SELECT 1", from_dialect="invalid", to_dialect="spark")
