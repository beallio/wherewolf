import streamlit as st
from pathlib import Path
from typing import Optional
from st_file_browser import st_file_browser


class FileBrowser:
    """A professional file explorer using st-file-browser."""

    @staticmethod
    def render_explorer(show_hidden: bool = False) -> Optional[str]:
        """Renders the st-file-browser component.

        Args:
            show_hidden: Whether to show hidden files.

        Returns:
            The selected file path if one was clicked, else None.
        """
        if "explorer_path" not in st.session_state:
            st.session_state.explorer_path = str(Path.cwd())

        current_path = st.session_state.explorer_path

        # Supported data file extensions
        valid_exts = [".csv", ".parquet", ".json"]

        # Build glob patterns based on supported extensions
        # If we wanted to filter specifically: glob_patterns=[f"**/*{ext}" for ext in valid_exts]
        # But for now we'll allow browsing everything and just handle selection

        event = st_file_browser(
            current_path,
            key="st_file_browser_v2",
            show_choose_file=True,
            glob_patterns=("**/*",) if show_hidden else ("**/[!.]*",),
        )

        if event:
            if event["type"] == "SELECT_FILE":
                selected_item = event["target"]
                # item['path'] is usually relative to the root 'current_path'
                full_path = Path(current_path) / selected_item["path"]

                # Check if it's one of our supported formats before returning
                if full_path.suffix.lower() in valid_exts:
                    return str(full_path)
                else:
                    st.warning(f"Unsupported file type: {full_path.suffix}")

        return None
