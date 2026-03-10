import os
import pytest
from streamlit.testing.v1 import AppTest


def test_app_handles_broken_symlinks(tmp_path):
    """
    Simulate app execution with a broken symlink in the explorer path.
    """
    # 1. Setup a directory with a broken symlink
    test_dir = tmp_path / "test_browse"
    test_dir.mkdir()

    broken_link = test_dir / "broken_link"
    target = tmp_path / "does_not_exist"
    os.symlink(target, broken_link)

    # 2. Run the App using AppTest
    at = AppTest.from_file("src/wherewolf/app.py")

    # 3. Set the explorer path in session state BEFORE running
    # Note: st.session_state in AppTest is set via at.session_state
    at.session_state.explorer_path = str(test_dir)
    at.session_state.path_input = ""

    at.run()

    # If it crashes, at.exception will be set or at.run() will raise
    if at.exception:
        error_msg = str(at.exception[0])
        if "FileNotFoundError" in error_msg or "No such file or directory" in error_msg:
            pytest.fail(f"App crashed with FileNotFoundError on broken symlink: {error_msg}")
        else:
            # Other exceptions might be unrelated to our core issue
            pass


if __name__ == "__main__":
    pytest.main([__file__])
