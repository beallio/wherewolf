from wherewolf.execution.spark_engine import SparkEngine


def test_spark_engine_init():
    engine = SparkEngine()
    assert engine is not None
