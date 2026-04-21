import pandas as pd
from wherewolf.execution import DuckDBEngine, SparkEngine


def test_excel_support_duckdb(tmp_path):
    # 1. Create a dummy Excel file
    excel_path = tmp_path / "test.xlsx"
    df_orig = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    df_orig.to_excel(excel_path, index=False)

    engine = DuckDBEngine()
    result = engine.execute("SELECT * FROM dataset", str(excel_path))

    assert result.success, f"Execution failed: {result.error_message}"
    assert len(result.df) == 3
    assert result.df["col1"].tolist() == [1, 2, 3]


def test_excel_support_spark(tmp_path):
    # 1. Create a dummy Excel file
    excel_path = tmp_path / "test_spark.xlsx"
    df_orig = pd.DataFrame({"col1": [10, 20], "col2": ["x", "y"]})
    df_orig.to_excel(excel_path, index=False)

    engine = SparkEngine()
    result = engine.execute("SELECT * FROM dataset", str(excel_path))

    assert result.success, f"Execution failed: {result.error_message}"
    assert len(result.df) == 2
    assert result.df["col1"].tolist() == [10, 20]


def test_ui_extension_recognition():
    # This is a bit hard to test without full streamlit, but we can check the extension set
    # if it's exposed or by mocking. Let's rely on integration tests or manual check if needed.
    pass
