from unittest.mock import patch
from wherewolf.ui.file_browser import FileBrowser


def test_file_browser_filtering(tmp_path):
    """Test that file browser filters files by extension but keeps directories."""
    # Create a dummy structure
    (tmp_path / "subdir").mkdir()
    (tmp_path / "data.csv").write_text("a,b\n1,2")
    (tmp_path / "data.parquet").write_text("dummy")
    (tmp_path / "data.json").write_text("{}")
    (tmp_path / "data.xlsx").write_text("dummy")
    (tmp_path / "data.xls").write_text("dummy")
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "script.py").write_text("print(1)")
    (tmp_path / ".hidden_dir").mkdir()
    (tmp_path / ".hidden_file.csv").write_text("a,b\n1,2")

    key = "wherewolf_fs"
    curr_dir_key = f"{key}_curr_dir"
    files_key = f"{key}_files"

    # Mock streamlit session state
    session_state = {curr_dir_key: str(tmp_path)}

    with (
        patch("streamlit.session_state", session_state),
        patch("streamlit.error"),
        patch("streamlit.write"),
        patch("streamlit.selectbox", return_value="Select file/folder..."),
        patch("streamlit.caption"),
    ):
        # Test default filtering (no hidden)
        FileBrowser.render_explorer(show_hidden=False)

        files = session_state[files_key]
        # Should contain: Placeholder, .., subdir, data.csv, data.parquet, data.json, data.xlsx, data.xls
        # Should NOT contain: notes.txt, script.py, .hidden_dir, .hidden_file.csv
        assert "subdir" in files
        assert "data.csv" in files
        assert "data.parquet" in files
        assert "data.json" in files
        assert "data.xlsx" in files
        assert "data.xls" in files
        assert "notes.txt" not in files
        assert "script.py" not in files
        assert ".hidden_dir" not in files
        assert ".hidden_file.csv" not in files
        assert ".." in files

        # Verify sorting: 'subdir' should come before files like 'data.csv'
        idx_subdir = files.index("subdir")
        idx_csv = files.index("data.csv")
        assert idx_subdir < idx_csv, "Directories should be sorted before files"

        # Test show_hidden=True
        FileBrowser.render_explorer(show_hidden=True)
        files_hidden = session_state[files_key]
        assert ".hidden_dir" in files_hidden
        assert ".hidden_file.csv" in files_hidden
        assert "notes.txt" not in files_hidden

        # Verify sorting with hidden: .hidden_dir should come before data.csv
        idx_hidden_dir = files_hidden.index(".hidden_dir")
        idx_csv_hidden = files_hidden.index("data.csv")
        assert idx_hidden_dir < idx_csv_hidden, "Hidden directories should be sorted before files"
