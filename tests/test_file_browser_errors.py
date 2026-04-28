from streamlit.testing.v1 import AppTest


def test_file_browser_filters_invalid_extension(tmp_path):
    """Verify file browser filters out unsupported file types."""
    # 1. Create files: one supported, one unsupported
    valid_file = tmp_path / "data.csv"
    valid_file.write_text("a,b\n1,2")
    invalid_file = tmp_path / "data.txt"
    invalid_file.write_text("not data")

    at = AppTest.from_file("src/wherewolf/app.py")

    # 2. Set the directory in session state
    at.session_state["wherewolf_fs_curr_dir"] = str(tmp_path)

    at.run()

    # 3. Verify that only the CSV file is in the selectbox options
    # The selectbox has key 'wherewolf_fs'
    fs_selectbox = at.selectbox(key="wherewolf_fs")
    options = fs_selectbox.options

    assert "data.csv" in options
    assert "data.txt" not in options
