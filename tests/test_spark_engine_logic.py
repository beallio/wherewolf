from unittest.mock import MagicMock, patch

import pyarrow as pa

from wherewolf.execution import SparkEngine


def test_spark_engine_execute_logic_parquet():
    """Verify SparkEngine logic for Parquet files using mocks."""
    with (
        patch("wherewolf.execution.spark_engine.SPARK_AVAILABLE", True),
        patch("wherewolf.execution.spark_engine.create_child_session") as create_child_session,
    ):
        mock_spark = MagicMock()
        create_child_session.return_value = mock_spark
        mock_df = MagicMock()
        mock_spark.read.parquet.return_value = mock_df
        mock_res = MagicMock()
        mock_spark.sql.return_value = mock_res
        mock_res.limit.return_value.toArrow.return_value = pa.table({"a": [1]})

        engine = SparkEngine()
        query = "SELECT * FROM dataset"
        path = "/tmp/test.parquet"

        result = engine.execute(query, path)

        # Verify interactions
        mock_spark.read.parquet.assert_called_once_with(path)
        mock_df.createOrReplaceTempView.assert_called_once_with("dataset")
        mock_spark.sql.assert_called_once_with(query)
        assert result.success is True


def test_spark_engine_unsupported_format():
    """Verify SparkEngine handles unsupported formats."""
    with (
        patch("wherewolf.execution.spark_engine.SPARK_AVAILABLE", True),
        patch("wherewolf.execution.spark_engine.create_child_session"),
    ):
        engine = SparkEngine()
        result = engine.execute("SELECT 1", "/tmp/test.txt")

        assert result.success is False
        assert "Unsupported file format" in result.error_message
