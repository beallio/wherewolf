from streamlit.testing.v1 import AppTest


def test_file_browser_invalid_extension(tmp_path):
    """Verify file browser warns about unsupported file types using AppTest."""
    # 1. Create an unsupported file
    invalid_file = tmp_path / "data.txt"
    invalid_file.write_text("not data")

    at = AppTest.from_file("src/wherewolf/app.py")

    # 2. Mock session state to simulate selecting this file in the browser
    # The browser key is 'wherewolf_fs'
    at.session_state["wherewolf_fs_curr_dir"] = str(tmp_path)
    at.session_state["wherewolf_fs_files"] = ["Select file/folder...", "data.txt"]
    at.session_state["wherewolf_fs"] = "data.txt"

    at.run()

    # 3. Check for the warning in the UI
    # In AppTest, warnings are usually captured in the element tree
    all_warnings = [w.body for w in at.warning]
    assert any("not a supported data format" in w for w in all_warnings)
