from streamlit.testing.v1 import AppTest
from unittest.mock import patch


def test_app_initialization():
    """Basic test to ensure the Streamlit app can be initialized."""
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    # Assert basic UI elements exist
    assert any("Wherewolf" in m.value for m in at.sidebar.markdown)
    assert not at.exception
    assert at.session_state.selected_query == "SELECT * FROM dataset LIMIT 10"


def test_query_updates_on_first_dataset():
    """Test that the query updates when the first dataset is loaded."""
    at = AppTest.from_file("src/wherewolf/app.py")

    # We mock render_explorer to return a path then None
    with patch("wherewolf.app.FileBrowser.render_explorer") as mock_render:
        mock_render.side_effect = ["/path/to/my_data.csv", None, None]
        at.run()

        # The alias for my_data.csv should be my_data
        assert at.session_state.selected_query == "SELECT * FROM my_data LIMIT 10"
        # The key for st_ace will have changed because of the counter
        assert at.session_state.editor_reset_counter == 1
        assert at.session_state.catalog["my_data"] == "/path/to/my_data.csv"


def test_query_does_not_update_on_second_dataset():
    """Test that the query does not update when a second dataset is loaded."""
    at = AppTest.from_file("src/wherewolf/app.py")

    with patch("wherewolf.app.FileBrowser.render_explorer") as mock_render:
        # Load first dataset
        mock_render.side_effect = ["/path/to/first.csv", None, None, None, None]
        at.run()
        assert at.session_state.selected_query == "SELECT * FROM first LIMIT 10"

        # Manually change query
        at.session_state.selected_query = "SELECT 1"

        # Load second dataset
        mock_render.side_effect = ["/path/to/second.csv", None, None]
        at.run()

        # Should still be the user's query
        assert at.session_state.selected_query == "SELECT 1"
        assert "first" in at.session_state.catalog
        assert "second" in at.session_state.catalog
