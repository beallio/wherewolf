from wherewolf.ui import FileBrowser


def test_file_browser_v2_interface():
    """Verify that the FileBrowser class still has the required method."""
    assert hasattr(FileBrowser, "render_explorer")
    # Check that it accepts the same arguments (default False)
    import inspect

    sig = inspect.signature(FileBrowser.render_explorer)
    assert "show_hidden" in sig.parameters
