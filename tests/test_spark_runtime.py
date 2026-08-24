from unittest.mock import MagicMock, patch

from wherewolf.execution import spark_runtime


def test_create_child_session_builds_one_bounded_root_and_returns_isolated_children() -> None:
    root = MagicMock()
    first_child = MagicMock()
    second_child = MagicMock()
    root.newSession.side_effect = (first_child, second_child)

    with patch("wherewolf.execution.spark_runtime.import_module") as import_module:
        spark_session = import_module.return_value.SparkSession
        (
            spark_session.builder.appName.return_value.master.return_value.config.return_value.config.return_value.config.return_value.config.return_value.getOrCreate.return_value
        ) = root
        spark_runtime.reset_spark_runtime_for_tests()
        try:
            assert spark_runtime.create_child_session() is first_child
            assert spark_runtime.create_child_session() is second_child
        finally:
            spark_runtime.reset_spark_runtime_for_tests()

    import_module.assert_called_once_with("pyspark.sql")
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
