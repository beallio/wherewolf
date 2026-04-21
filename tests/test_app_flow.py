import pandas as pd
from streamlit.testing.v1 import AppTest


def test_app_query_execution_flow(tmp_path):
    """Simulate selecting a file and running a query via DuckDB."""
    # 1. Create a dummy CSV
    csv_file = tmp_path / "app_test.csv"
    pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}).to_csv(csv_file, index=False)

    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    # 2. Inject path and query into session state (simulating browser selection)
    at.session_state.path_input = str(csv_file)
    at.session_state.selected_query = "SELECT * FROM dataset"
    at.run()

    # 3. Trigger 'Run' button
    run_btn = next(b for b in at.button if b.label == "Run")
    run_btn.click().run()

    # 3.5 Run again to process the completed future
    # Since it's a fast query on a small local file, it should be done.
    # In AppTest, we might need to wait a bit or just run again.
    import time

    time.sleep(0.5)
    at.run()

    # 4. Assert results exist in UI
    assert any("Rows" in m.label for m in at.metric)
    assert len(at.dataframe) > 0
    assert at.dataframe[0].value.shape[0] == 3


def test_app_clear_history():
    """Verify the clear history button works in the UI."""
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    # Find clear history button
    clear_btn = next(b for b in at.button if b.label == "Clear History")
    clear_btn.click().run()

    # Search ALL sidebar markdown elements for the empty history message
    all_sidebar_text = " ".join([m.value for m in at.sidebar.markdown])
    assert "No history yet." in all_sidebar_text


def test_translation_target_options():
    """Verify that translation targets exclude the input dialect."""
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    # Simulate a successful execution with DuckDB as input
    at.session_state.path_input = "/tmp/fake.csv"
    at.session_state.input_dialect_ui = "DuckDB"
    # We need a query result to show the translation section
    from wherewolf.execution import QueryResult
    import pandas as pd

    at.session_state.query_result = QueryResult(df=pd.DataFrame({"a": [1]}), success=True)
    at.session_state.executed_input_dialect_key = "duckdb"
    at.run()

    # Find the Target Dialect selectbox
    # It's the one in the translation section (after the sidebar ones)
    target_selectbox = next(s for s in at.selectbox if s.label == "Target Dialect")

    # Should contain Spark and Azure SQL, but NOT DuckDB
    assert "DuckDB" not in target_selectbox.options
    assert "Spark" in target_selectbox.options
    assert "Azure SQL" in target_selectbox.options
