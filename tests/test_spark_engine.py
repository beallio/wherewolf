import polars as pl
import pytest

from wherewolf.execution.spark_engine import SparkEngine


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "test.csv"
    df = pl.DataFrame({"name": ["alice", "bob", "charlie"], "value": [100, 200, 300]})
    df.write_csv(path)
    return str(path)


@pytest.mark.spark
def test_spark_get_schema(csv_path, spark_session):
    engine = SparkEngine()
    schema_df = engine.get_schema(csv_path)

    assert isinstance(schema_df, pl.DataFrame)
    assert list(schema_df.columns) == ["Column", "Type"]
    assert "name" in schema_df["Column"].to_list()
    assert "value" in schema_df["Column"].to_list()


@pytest.mark.spark
def test_spark_session_is_memory_bounded(spark_session):
    assert spark_session.sparkContext.master == "local[1]"
    assert spark_session.conf.get("spark.driver.memory") == "512m"
    assert spark_session.conf.get("spark.ui.enabled") == "false"
    assert spark_session.conf.get("spark.sql.shuffle.partitions") == "1"


def test_spark_engine_init():
    engine = SparkEngine()
    assert engine is not None
