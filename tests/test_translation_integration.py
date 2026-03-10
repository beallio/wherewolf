import pytest
import os
from wherewolf.translation import Translator
from wherewolf.execution import DuckDBEngine


@pytest.fixture
def csv_path():
    return os.path.abspath("tests/test_data.csv")


@pytest.fixture
def translator():
    return Translator()


def test_aggregate_translation(translator):
    """Test translation of a simple aggregate query."""
    duck_sql = "SELECT region, AVG(loan_amount) as avg_loan FROM dataset GROUP BY region"
    spark_sql = translator.translate(duck_sql, from_dialect="duckdb", to_dialect="spark")

    assert "AVG" in spark_sql.upper()
    assert "GROUP BY" in spark_sql.upper()
    assert "REGION" in spark_sql.upper()


def test_timestamp_filter_translation(translator):
    """Test translation of timestamp filtering."""
    # Note: DuckDB and Spark often have different timestamp literal expectations
    duck_sql = "SELECT * FROM dataset WHERE application_date > '2026-03-08 12:00:00'"
    spark_sql = translator.translate(duck_sql, from_dialect="duckdb", to_dialect="spark")

    assert "SELECT" in spark_sql.upper()
    assert "APPLICATION_DATE" in spark_sql.upper()
    assert "2026-03-08" in spark_sql


def test_string_func_translation(translator):
    """Test translation of string functions."""
    duck_sql = "SELECT full_name, UPPER(city) as city_upper FROM dataset"
    spark_sql = translator.translate(duck_sql, from_dialect="duckdb", to_dialect="spark")

    assert "UPPER" in spark_sql.upper()
    assert "FULL_NAME" in spark_sql.upper()


def test_window_func_translation(translator):
    """Test translation of window functions."""
    duck_sql = "SELECT loan_id, ROW_NUMBER() OVER (PARTITION BY grade ORDER BY loan_amount DESC) as rank FROM dataset"
    spark_sql = translator.translate(duck_sql, from_dialect="duckdb", to_dialect="spark")

    assert "ROW_NUMBER" in spark_sql.upper()
    assert "OVER" in spark_sql.upper()
    assert "PARTITION BY" in spark_sql.upper()
    assert "GRADE" in spark_sql.upper()


def test_duckdb_execution_of_translated_sql(translator, csv_path):
    """Verify that a query translated from Spark to DuckDB actually runs in DuckDB."""
    engine = DuckDBEngine()
    # Query in Spark dialect
    spark_sql = "SELECT grade, count(*) as cnt FROM dataset GROUP BY grade HAVING count(*) > 1"

    # Translate to DuckDB
    duck_sql = translator.translate(spark_sql, from_dialect="spark", to_dialect="duckdb")

    # Execute in DuckDB
    result = engine.execute(duck_sql, csv_path)

    assert result.success is True
    assert result.row_count > 0
    assert "grade" in result.df.columns


def test_translation_to_tsql_integration(translator):
    """Verify translation of complex queries to Azure SQL (T-SQL)."""
    duck_sql = "SELECT LEFT(full_name, 5) as short_name FROM dataset"
    tsql_sql = translator.translate(duck_sql, from_dialect="duckdb", to_dialect="tsql")

    assert "LEFT" in tsql_sql.upper()
    assert "SHORT_NAME" in tsql_sql.upper()
