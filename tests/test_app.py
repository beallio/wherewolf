from streamlit.testing.v1 import AppTest


def test_app_initialization():
    """Basic test to ensure the Streamlit app can be initialized."""
    # We point to the app file. AppTest will simulate the run.
    at = AppTest.from_file("src/wherewolf/app.py")
    at.run()

    # Assert basic UI elements exist
    assert any("Wherewolf" in m.value for m in at.sidebar.markdown)
    assert at.header[0].value == "SQL Editor"
    assert not at.exception
