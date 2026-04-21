import pandas as pd
import pytest
from wherewolf.execution.spark_engine import SparkEngine, SPARK_AVAILABLE


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "test.csv"
    df = pd.DataFrame({"name": ["alice", "bob", "charlie"], "value": [100, 200, 300]})
    df.to_csv(path, index=False)
    return str(path)


@pytest.mark.skipif(not SPARK_AVAILABLE, reason="PySpark not installed")
def test_spark_get_schema(csv_path):
    engine = SparkEngine()
    schema_df = engine.get_schema(csv_path)

    assert isinstance(schema_df, pd.DataFrame)
    assert list(schema_df.columns) == ["Column", "Type"]
    assert "name" in schema_df["Column"].values
    assert "value" in schema_df["Column"].values


def test_spark_engine_init():
    engine = SparkEngine()
    assert engine is not None
