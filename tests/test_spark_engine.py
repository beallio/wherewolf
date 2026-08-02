import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import MagicMock, patch
from uuid import uuid4

import polars as pl
import pyarrow as pa
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


def test_spark_engine_creates_a_memory_bounded_session_lazily_and_reuses_it():
    with (
        patch("wherewolf.execution.spark_engine.SPARK_AVAILABLE", True),
        patch("wherewolf.execution.spark_engine.import_module") as import_module,
    ):
        spark_session = import_module.return_value.SparkSession
        session = MagicMock()
        (
            spark_session.builder.appName.return_value.master.return_value.config.return_value.config.return_value.config.return_value.config.return_value.getOrCreate.return_value.newSession.return_value
        ) = session

        engine = SparkEngine()

        import_module.assert_not_called()
        assert engine._get_session() is session
        assert engine._get_session() is session

        spark_session.builder.appName.assert_called_once_with("Wherewolf")
        spark_session.builder.appName.return_value.master.assert_called_once_with("local[1]")
        builder = spark_session.builder.appName.return_value.master.return_value
        builder.config.assert_called_once_with("spark.driver.memory", "512m")
        builder.config.return_value.config.assert_called_once_with("spark.ui.enabled", "false")
        builder.config.return_value.config.return_value.config.assert_called_once_with(
            "spark.sql.shuffle.partitions", "1"
        )
        builder.config.return_value.config.return_value.config.return_value.config.assert_called_once_with(
            "spark.sql.execution.arrow.pyspark.enabled", "true"
        )
        builder.config.return_value.config.return_value.config.return_value.config.return_value.getOrCreate.assert_called_once_with()


def test_spark_engine_startup_failure_is_actionable():
    with (
        patch("wherewolf.execution.spark_engine.SPARK_AVAILABLE", True),
        patch("wherewolf.execution.spark_engine.import_module") as import_module,
    ):
        spark_session = import_module.return_value.SparkSession
        spark_session.builder.appName.return_value.master.return_value.config.return_value.config.return_value.config.return_value.config.return_value.getOrCreate.side_effect = RuntimeError(
            "gateway failed"
        )

        result = SparkEngine().execute("SELECT 1")

    assert result.success is False
    assert "wherewolf[spark]" in result.error_message
    assert "java" in result.error_message.lower()


def test_spark_engine_cancels_only_its_request_job_group():
    first_request = uuid4()
    second_request = uuid4()
    shared_context = MagicMock()

    first = SparkEngine(request_id=first_request)
    second = SparkEngine(request_id=second_request)
    first.spark = MagicMock(sparkContext=shared_context)
    second.spark = MagicMock(sparkContext=shared_context)

    first.interrupt()

    shared_context.cancelJobGroup.assert_called_once_with(str(first_request))
    assert str(second_request) not in [
        str(call) for call in shared_context.cancelJobGroup.call_args_list
    ]
    assert "cancelAllJobs" not in Path("src/wherewolf/execution/spark_engine.py").read_text()


@pytest.mark.parametrize("error", [RuntimeError("bad query"), RuntimeError("cancelled")])
@patch("wherewolf.execution.spark_engine.SPARK_AVAILABLE", True)
def test_spark_engine_drops_request_temp_views_after_a_failed_or_cancelled_query(error):
    engine = SparkEngine()
    engine.spark = MagicMock()
    registered = MagicMock()
    engine.spark.read.option.return_value.option.return_value.csv.return_value = registered
    engine.spark.sql.side_effect = error

    result = engine.execute("SELECT broken", path="/tmp/events.csv")

    assert result.success is False
    engine.spark.catalog.dropTempView.assert_called_once_with("dataset")


@patch("wherewolf.execution.spark_engine.SPARK_AVAILABLE", True)
def test_two_concurrent_spark_requests_cancel_only_their_own_job_group():
    first_request = uuid4()
    second_request = uuid4()
    shared_context = MagicMock()
    barrier = Barrier(2)
    shared_context.setJobGroup.side_effect = lambda *args, **kwargs: barrier.wait()

    def configured_engine(request_id):
        engine = SparkEngine(request_id=request_id)
        engine.spark = MagicMock(sparkContext=shared_context)
        engine.spark.sql.return_value.limit.return_value.toArrow.return_value = pa.table(
            {"id": [1]}
        )
        return engine

    first = configured_engine(first_request)
    second = configured_engine(second_request)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first.execute, "SELECT 1", limit=1)
        second_future = executor.submit(second.execute, "SELECT 1", limit=1)
        first_result = first_future.result()
        second_result = second_future.result()

    first.interrupt()

    assert first_result.success is True
    assert second_result.success is True
    assert {call.args[0] for call in shared_context.setJobGroup.call_args_list} == {
        str(first_request),
        str(second_request),
    }
    shared_context.cancelJobGroup.assert_called_once_with(str(first_request))


@pytest.mark.spark
def test_spark_adapter_converts_preview_rows_columns_and_truncation(tmp_path, spark_session):
    from wherewolf.domain import EngineKind, ExecutionStatus
    from wherewolf.execution.registry import EngineRegistry
    from wherewolf.services.catalog_service import CatalogService
    from wherewolf.services.execution_request_builder import ExecutionRequestBuilder

    path = tmp_path / "events.csv"
    pl.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]}).write_csv(path)
    catalog_service = CatalogService()
    catalog_service.add_paths((path,))
    request = ExecutionRequestBuilder.build(
        sql="SELECT id, name FROM events ORDER BY id",
        source_dialect="spark",
        engine=EngineKind.SPARK,
        catalog_service=catalog_service,
        preview_limit=2,
    )

    result = EngineRegistry().create(EngineKind.SPARK, request.request_id).execute_preview(request)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.frame is not None
    assert result.frame.columns == ["id", "name"]
    assert result.frame.rows() == [(1, "a"), (2, "b")]
    assert result.preview_row_count == 2
    assert result.truncated is True


def test_spark_engine_rejects_json_content_that_does_not_match_its_suffix(tmp_path):
    jsonl_path = tmp_path / "events.jsonl"
    jsonl_path.write_text('[{"id": 1}]')

    with pytest.raises(ValueError, match="JSON Lines"):
        SparkEngine._validate_json_shape(jsonl_path)


@pytest.mark.spark
def test_spark_engine_reads_json_array_and_json_lines(tmp_path, spark_session):
    array_path = tmp_path / "events.json"
    lines_path = tmp_path / "events.jsonl"
    source = pl.DataFrame({"id": [1, 2]})
    array_path.write_text(json.dumps(source.to_dicts(), indent=2))
    source.write_ndjson(lines_path)

    engine = SparkEngine()
    array_result = engine.execute("SELECT count(*) AS count FROM dataset", str(array_path))
    lines_result = engine.execute("SELECT count(*) AS count FROM dataset", str(lines_path))

    assert array_result.success is True
    assert lines_result.success is True
    assert array_result.df is not None
    assert lines_result.df is not None
    assert array_result.df["count"].to_list() == [2]
    assert lines_result.df["count"].to_list() == [2]
