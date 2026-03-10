import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import streamlit as st

# Mock Streamlit bits before importing components
if "explorer_path" not in st.session_state:
    st.session_state.explorer_path = ""

from wherewolf.ui import FileBrowser


def test_file_browser_handles_broken_symlinks(tmp_path):
    """
    Reproduce FileNotFoundError when a directory contains a broken symlink.
    st-file-browser walks the tree and calls os.stat, which fails on broken links.
    """
    # 1. Setup a directory with a broken symlink
    test_dir = tmp_path / "test_browse"
    test_dir.mkdir()

    broken_link = test_dir / "broken_link"
    target = tmp_path / "does_not_exist"
    os.symlink(target, broken_link)

    # 2. Mock st.session_state
    with patch("streamlit.session_state", {"explorer_path": str(test_dir)}):
        # 3. Mock st components to avoid "Missing ScriptRunContext"
        with (
            patch("streamlit.sidebar"),
            patch("streamlit.expander"),
            patch("streamlit.checkbox", return_value=False),
            patch("streamlit.write"),
            patch("streamlit.columns", return_value=(MagicMock(), MagicMock())),
            patch("streamlit.button", return_value=False),
            patch("streamlit.rerun"),
            patch("streamlit.error"),
            patch("streamlit.warning"),
            patch("streamlit.code"),
        ):
            # This call is expected to raise FileNotFoundError based on user report
            # if the fix isn't applied inside the component or wrapper.
            try:
                FileBrowser.render_explorer(show_hidden=False)
            except FileNotFoundError:
                pytest.fail("FileBrowser crashed with FileNotFoundError on broken symlink")
            except Exception as e:
                # We want to catch the specific error reported
                if "No such file or directory" in str(e):
                    pytest.fail(f"FileBrowser crashed with: {e}")
                # Other streamlit-related errors are expected in a non-streamlit environment
                pass


if __name__ == "__main__":
    # Manual run for debugging
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        test_file_browser_handles_broken_symlinks(p)
        print("Success: Issue not reproduced or handled.")
