import os
import pytest
from unittest.mock import patch
from wherewolf.ui import FileBrowser


def test_navigate_to_parent_updates_state(tmp_path):
    """
    Reproduce the issue: Selecting '..' should update explorer_path to the parent directory.
    Real directories must exist for os.path.isdir to pass.
    """
    # 1. Setup real directory structure
    root = tmp_path / "root"
    child = root / "a" / "b" / "c"
    child.mkdir(parents=True)
    parent_dir = child.parent

    # 2. Mock session state
    key = "wherewolf_fs"
    session_state_dict = {
        key: "..",
        f"{key}_curr_dir": str(child),
        f"{key}_files": ["Select file/folder...", "..", "some_dir"],
    }

    # We patch st.session_state in the module where it's used
    with patch("wherewolf.ui.file_browser.st.session_state", session_state_dict):
        # 3. Trigger the callback
        FileBrowser._update_dir(key)

        # 4. Verify the current directory was updated to parent
        expected_path = os.path.normpath(str(parent_dir))
        actual_path = session_state_dict[f"{key}_curr_dir"]

        assert actual_path == expected_path, f"Expected {expected_path}, but got {actual_path}"


if __name__ == "__main__":
    pytest.main([__file__])
