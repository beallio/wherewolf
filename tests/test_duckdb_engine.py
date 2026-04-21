import pandas as pd
import pytest
from wherewolf.execution import DuckDBEngine, SparkEngine


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "test.csv"
    df = pd.DataFrame({"name": ["alice", "bob", "charlie"], "value": [100, 200, 300]})
    df.to_csv(path, index=False)
    return str(path)


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


def test_duckdb_get_schema(csv_path):
    engine = DuckDBEngine()
    schema_df = engine.get_schema(csv_path)

    assert isinstance(schema_df, pd.DataFrame)
    # DuckDB's DESCRIBE returns many columns, but our HUD should normalize to ["Column", "Type"]
    assert list(schema_df.columns) == ["Column", "Type"]
    assert "name" in schema_df["Column"].values
    assert "value" in schema_df["Column"].values


@pytest.mark.skip(reason="Spark requires complex setup for CI, focus on DuckDB first")
def test_spark_engine_success(csv_path):
    engine = SparkEngine()
    query = "SELECT * FROM dataset WHERE value > 150"
    result = engine.execute(query, csv_path, limit=100)

    assert result.success is True
    assert len(result.df) == 2
