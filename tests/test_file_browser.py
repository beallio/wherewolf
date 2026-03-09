from wherewolf.ui import FileBrowser


def test_file_browser_smoke():
    """Smoke test for FileBrowser (cannot test UI popups easily)."""
    # Verify the class and methods exist
    assert hasattr(FileBrowser, "select_file")
    assert hasattr(FileBrowser, "select_directory")
