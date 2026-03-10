from unittest.mock import MagicMock, patch
from wherewolf.execution import SparkEngine


def test_spark_engine_execute_logic_parquet():
    """Verify SparkEngine logic for Parquet files using mocks."""
    with (
        patch("wherewolf.execution.spark_engine.SPARK_AVAILABLE", True),
        patch("wherewolf.execution.spark_engine.SparkSession") as mock_spark_session,
    ):
        # Setup mock chain
        mock_spark = mock_spark_session.builder.appName.return_value.master.return_value.getOrCreate.return_value
        mock_df = MagicMock()
        mock_spark.read.parquet.return_value = mock_df

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
        patch("wherewolf.execution.spark_engine.SparkSession"),
    ):
        engine = SparkEngine()
        result = engine.execute("SELECT 1", "/tmp/test.txt")

        assert result.success is False
        assert "Unsupported file format" in result.error_message
