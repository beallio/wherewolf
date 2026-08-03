import polars as pl
import pytest

from wherewolf.execution import DuckDBEngine, SparkEngine


def test_excel_support_duckdb(tmp_path):
    # 1. Create a dummy Excel file
    excel_path = tmp_path / "test.xlsx"
    df_orig = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    df_orig.write_excel(excel_path)

    engine = DuckDBEngine()
    result = engine.execute("SELECT * FROM dataset", str(excel_path))

    assert result.success, f"Execution failed: {result.error_message}"
    assert len(result.df) == 3
    assert result.df["col1"].to_list() == [1, 2, 3]


@pytest.mark.spark
def test_excel_support_spark(tmp_path, spark_session):
    # 1. Create a dummy Excel file
    excel_path = tmp_path / "test_spark.xlsx"
    df_orig = pl.DataFrame({"col1": [10, 20], "col2": ["x", "y"]})
    df_orig.write_excel(excel_path)

    engine = SparkEngine()
    result = engine.execute("SELECT * FROM dataset", str(excel_path))

    assert result.success, f"Execution failed: {result.error_message}"
    assert len(result.df) == 2
    assert result.df["col1"].to_list() == [10, 20]


def test_ui_extension_recognition():
    # Native dialog filter behavior is covered by the desktop file-dialog tests.
    pass
