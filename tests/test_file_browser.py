from wherewolf.ui import FileBrowser


def test_file_browser_smoke():
    """Smoke test for FileBrowser (Streamlit-native)."""
    # Verify the class and methods exist
    assert hasattr(FileBrowser, "render_explorer")
