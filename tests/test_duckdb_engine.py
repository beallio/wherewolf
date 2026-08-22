import polars as pl
import pytest

from wherewolf.execution import DuckDBEngine, SparkEngine


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "test.csv"
    df = pl.DataFrame({"name": ["alice", "bob", "charlie"], "value": [100, 200, 300]})
    df.write_csv(path)
    return str(path)


@pytest.fixture
def jsonl_path(tmp_path):
    path = tmp_path / "test.jsonl"
    path.write_text('{"id": 1, "name": "a"}\n{"id": 2, "name": "b"}\n')
    return str(path)


def test_duckdb_engine_success(csv_path):
    engine = DuckDBEngine()
    # Query must use the reserved name 'dataset'
    query = "SELECT * FROM dataset WHERE value > 150"
    result = engine.execute(query, csv_path, limit=100)

    assert result.success is True
    assert len(result.df) == 2
    assert "bob" in result.df["name"].to_list()
    assert result.execution_time > 0
    assert result.row_count == 2


@pytest.fixture
def large_csv_path(tmp_path):
    path = tmp_path / "large.csv"
    df = pl.DataFrame({"value": list(range(5))})
    df.write_csv(path)
    return str(path)


def test_duckdb_engine_limit_truncates(large_csv_path):
    engine = DuckDBEngine()
    result = engine.execute("SELECT * FROM dataset", large_csv_path, limit=2)

    assert result.success is True
    assert result.row_count == 2
    assert result.is_truncated is True


def test_duckdb_engine_none_limit_returns_full_result(large_csv_path):
    engine = DuckDBEngine()
    result = engine.execute("SELECT * FROM dataset", large_csv_path, limit=None)

    assert result.success is True
    assert result.row_count == 5
    assert len(result.df) == 5
    assert result.is_truncated is False
    assert result.df["value"].to_list() == [0, 1, 2, 3, 4]


def test_duckdb_engine_failure(csv_path):
    engine = DuckDBEngine()
    # Invalid SQL
    query = "SELECT * FROM nonexistent"
    result = engine.execute(query, csv_path, limit=100)

    assert result.success is False
    assert result.error_message != ""


def test_duckdb_engine_treats_bound_injection_value_as_data(csv_path):
    engine = DuckDBEngine()
    injection = "'; DROP TABLE dataset; --"

    result = engine.execute("SELECT ? AS value", csv_path, params=[injection])

    assert result.success is True
    assert result.df["value"].to_list() == [injection]
    assert engine.execute("SELECT count(*) AS count FROM dataset", csv_path).success is True


def test_duckdb_get_schema(csv_path):
    engine = DuckDBEngine()
    schema_df = engine.get_schema(csv_path)

    assert isinstance(schema_df, pl.DataFrame)
    # DuckDB's DESCRIBE returns many columns, but our HUD should normalize to ["Column", "Type"]
    assert list(schema_df.columns) == ["Column", "Type"]
    assert "name" in schema_df["Column"].to_list()
    assert "value" in schema_df["Column"].to_list()


def test_duckdb_engine_reads_json_lines_as_typed_columns(jsonl_path):
    engine = DuckDBEngine()

    result = engine.execute("SELECT * FROM dataset ORDER BY id", jsonl_path)

    assert result.success is True
    assert result.df.schema == {"id": pl.Int64, "name": pl.String}
    assert result.df.to_dicts() == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]


def test_duckdb_get_schema_reads_json_lines_fields(jsonl_path):
    engine = DuckDBEngine()

    schema_df = engine.get_schema(jsonl_path)

    assert schema_df.to_dicts() == [
        {"Column": "id", "Type": "BIGINT"},
        {"Column": "name", "Type": "VARCHAR"},
    ]


def test_duckdb_engine_reports_unsupported_source_format(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("not a dataset")
    engine = DuckDBEngine()

    result = engine.execute("SELECT * FROM dataset", str(path))

    assert result.success is False
    assert "Unsupported source format: .txt" in result.error_message


@pytest.mark.spark
def test_spark_engine_success(csv_path, spark_session):
    engine = SparkEngine()
    query = "SELECT * FROM dataset WHERE value > 150"
    result = engine.execute(query, csv_path, limit=100)

    assert result.success is True
    assert len(result.df) == 2
