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
    run_btn = at.button[0]  # The '🚀 Run' button
    assert run_btn.label == "🚀 Run"
    run_btn.click().run()

    # 4. Assert results exist in UI
    assert any("Rows Returned" in m.label for m in at.metric)
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
