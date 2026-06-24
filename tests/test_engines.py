import pytest
from wherewolf.engines import get_engine
from wherewolf.execution import DuckDBEngine, SparkEngine


def test_get_engine_duckdb():
    assert isinstance(get_engine("DuckDB"), DuckDBEngine)


def test_get_engine_spark():
    assert isinstance(get_engine("Spark"), SparkEngine)


def test_get_engine_unknown_raises():
    with pytest.raises(ValueError):
        get_engine("Sqlite")
