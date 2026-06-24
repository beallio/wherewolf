import polars as pl
from streamlit.testing.v1 import AppTest
from wherewolf.execution import QueryResult


def test_results_rendering_success():
    """Verify ResultsView renders properly on success."""
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    at.session_state.catalog = {"dataset": "/tmp/fake.csv"}
    at.session_state.query_result = QueryResult(df=pl.DataFrame({"a": [1]}), success=True)
    at.session_state.executed_input_dialect_key = "duckdb"
    at.session_state.executed_engine_name = "DuckDB"
    at.session_state.executed_engine_query = "SELECT 1 as a"
    at.session_state.executed_query = "SELECT 1 as a"
    at.run()

    assert not at.exception
    # Should have Translation section
    assert any("SQL Translation" in sub.value for sub in at.subheader)
    # Should have Export section
    assert any("Export Results" in sub.value for sub in at.subheader)


def test_results_rendering_failure():
    """Verify ResultsView renders properly on failure."""
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    at.session_state.catalog = {"dataset": "/tmp/fake.csv"}
    at.session_state.query_result = QueryResult(success=False, error_message="Syntax Error")
    at.run()

    assert not at.exception
    assert any("Query Failed" in e.value for e in at.error)
    assert any("Syntax Error" in t.value for t in at.text)
