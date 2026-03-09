import pytest
from wherewolf.execution import DuckDBEngine, SparkEngine


@pytest.fixture
def csv_path():
    return "/tmp/wherewolf/test.csv"


def test_duckdb_engine_success(csv_path):
    engine = DuckDBEngine()
    # Query must use the reserved name 'dataset'
    query = "SELECT * FROM dataset WHERE value > 150"
    result = engine.execute(query, csv_path, limit=100)

    assert result.success is True
    assert len(result.df) == 2
    assert "bob" in result.df["name"].values
    assert result.execution_time > 0
    assert result.row_count == 2


def test_duckdb_engine_failure(csv_path):
    engine = DuckDBEngine()
    # Invalid SQL
    query = "SELECT * FROM nonexistent"
    result = engine.execute(query, csv_path, limit=100)

    assert result.success is False
    assert result.error_message != ""


@pytest.mark.skip(reason="Spark requires complex setup for CI, focus on DuckDB first")
def test_spark_engine_success(csv_path):
    engine = SparkEngine()
    query = "SELECT * FROM dataset WHERE value > 150"
    result = engine.execute(query, csv_path, limit=100)

    assert result.success is True
    assert len(result.df) == 2
